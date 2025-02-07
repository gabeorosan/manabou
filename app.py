from fasthtml.common import *
import random
import re
from pathlib import Path
import google.generativeai as genai
import os
import time
from fasthtml.components import Zero_md, HTML, RawHTML
import asyncio

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")
app, rt = fast_app()

VOCAB_FILE = "vocab.txt"
# --- Ratio Control ---
REVIEW_TO_NEW_RATIO = 0.5  # 0.5 means 50% review, 50% new.  0.8 means 80% review, 20% new.
# --- End Ratio Control ---

async def get_explanation(question_data, selected_answer=None):
    is_correct_bool = selected_answer == question_data['answer'] if selected_answer else True

    prompt_text = f"""
    Given the following japanese definition, and words:
    Definition: {question_data['question']}
    Words: {question_data['options']}
    Format your output as follows, with no other text, and no romaji:
    Translation: [English translation of the definition]\n
    1. [Word 1] ([Furigana for Word 1]) - [English translation of Word 1]
    2. [Word 2] ([Furigana for Word 2]) - [English translation of Word 2]
    3. [Word 3] ([Furigana for Word 3]) - [English translation of Word 3]
    4. [Word 4] ([Furigana for Word 4]) - [English translation of Word 4]

    [Concise one-line explanation of the correct answer]\n
    """

    if not is_correct_bool and selected_answer:
        prompt_text += f"[Concise one-line explanation of why '{selected_answer}' is incorrect]"

    print(prompt_text)

    for attempt in range(10):
        try:
            response = await model.generate_content_async(prompt_text)
            return response.text.strip().replace("Translation: ", "")
        except Exception as e:
            print(f"Explanation generation failed with model {model}, attempt {attempt + 1}: {e}")
            if attempt < 9:
                await asyncio.sleep(5)
    return "Sorry, couldn't generate explanation."

async def generate_question_gemini(known_words):
    if not known_words:
        return await generate_new_word_question(known_words)  # Always new word if no known words

    # Use the REVIEW_TO_NEW_RATIO to control the probability
    if random.random() < REVIEW_TO_NEW_RATIO:  # Use random.random() for a float comparison
        return await generate_known_word_question(known_words)
    else:
        return await generate_new_word_question(known_words)


async def generate_new_word_question(known_words):
    if not known_words:
        vocab_str = "No known vocabulary yet."
    else:
        vocab_str = ", ".join(known_words)

    prompt = f"""
Vocab words: {vocab_str}

Based on the preceding list of vocab words, create a new word at a similar or slightly higher level of difficulty to add to the list, create a Japanese definition for that word to use as a multiple choice question, and choose three other words to use as incorrect multiple choice options. The new word must be a word that is not already in the list of known words, and it must be the only word that matches the definition so that the answer is unambiguous. Put the correct answer as option number 1. Do not put furigana or romaji.

Format the output as follows, with no other text:
Definition: [Japanese definition/description]
1) [correct option]
2) [incorrect option]
3) [incorrect option]
4) [incorrect option]
"""

    for attempt in range(10):
        try:
            response = await model.generate_content_async(prompt)
            response_text = response.text.strip()
            print(f"Gemini Output (Attempt {attempt + 1}):\n{response_text}")  # Print the raw output

            question_data = {}
            lines = response_text.strip().split('\n')

            # Remove empty lines
            lines = [line for line in lines if line.strip()]

            if len(lines) < 5:
                print(f"Parsing failed with model {model}, attempt {attempt + 1}")
                continue

            question_data["question"] = lines[0].split(': ', 1)[1].strip()
            options_list = [line.split(') ', 1)[1].strip() for line in lines[1:5]]
            question_data["options"] = options_list
            question_data["answer"] = options_list[0]
            return question_data

        except Exception as e:
            print(f"Request Error (Attempt {attempt + 1}): {e}")  # Print request errors
            print(f"Question generation failed with model {model}, attempt {attempt+1}: {e}")
        if attempt < 9:
            await asyncio.sleep(5)

    return None



async def generate_known_word_question(known_words):
    if not known_words:
        return None  # Should not happen, but handle gracefully

    # Choose a random word from the known words
    target_word = random.choice(known_words)

    prompt = f"""
Create a Japanese definition for the word: {target_word}.  Also, choose three other words from the following list to use as incorrect multiple choice options: {', '.join(known_words)}.  The definition must be specific enough that '{target_word}' is clearly the only correct answer among the four options. Do not put furigana or romaji.  Put the correct answer ({target_word}) as option number 1.

Format the output as follows, with no other text:
Definition: [Japanese definition/description]
1) [correct option]
2) [incorrect option]
3) [incorrect option]
4) [incorrect option]
"""

    for attempt in range(10):
        try:
            response = await model.generate_content_async(prompt)
            response_text = response.text.strip()
            print(f"Gemini Output (Attempt {attempt + 1}):\n{response_text}")

            question_data = {}
            lines = response_text.strip().split('\n')

            # Remove empty lines
            lines = [line for line in lines if line.strip()]

            if len(lines) < 5:
                print(f"Parsing failed with model {model}, attempt {attempt + 1}")
                continue

            question_data["question"] = lines[0].split(': ', 1)[1].strip()
            options_list = [line.split(') ', 1)[1].strip() for line in lines[1:5]]
            question_data["options"] = options_list

            # Ensure the correct answer is the target word
            if options_list[0] != target_word:
                print(f"Correct answer mismatch (Attempt {attempt + 1}). Expected {target_word}, got {options_list[0]}")
                continue # Retry if correct answer is not the expected.
            question_data["answer"] = options_list[0]
            return question_data

        except Exception as e:
            print(f"Request Error (Attempt {attempt + 1}): {e}")
            print(f"Question generation failed with model {model}, attempt {attempt+1}: {e}")
        if attempt < 9:
            await asyncio.sleep(5)
    return None



def load_word_progress():
    path = Path(VOCAB_FILE)
    if path.exists():
        return path.read_text().splitlines()
    else:
        return []

def save_word_progress(known_words):
    path = Path(VOCAB_FILE)
    path.write_text("\n".join(known_words))

def update_word_progress(word, correct, known_words):
    # ALWAYS add the word, regardless of correctness
    if word not in known_words:
        known_words.append(word)
        save_word_progress(known_words)
    return known_words


def get_due_card_fraction(known_words):
    return 0, len(known_words)

known_words = load_word_progress()
next_question_data = None
current_question_data = None
current_explanation = None
prefetch_lock = asyncio.Lock()


async def prefetch_next_question():
    global next_question_data, known_words, prefetch_lock
    async with prefetch_lock:
        if next_question_data is None:
            question_data = await generate_question_gemini(known_words)
            if question_data:
                question_data['word_to_review'] = question_data['answer']
                next_question_data = question_data


async def prefetch_explanation_and_next_question():
    global current_question_data, current_explanation, next_question_data, known_words, prefetch_lock

    async with prefetch_lock:
        if current_question_data:
            current_explanation = await get_explanation(current_question_data)

        question_data = await generate_question_gemini(known_words)
        if question_data:
            question_data['word_to_review'] = question_data['answer']
            next_question_data = question_data


async def get_next_question():
    global next_question_data, current_question_data, current_explanation
    if current_question_data is None:
        question_data = await generate_question_gemini(known_words)
        if question_data:
              question_data['word_to_review'] = question_data['answer']
              current_question_data = question_data
        else:
            return None, None
        options = current_question_data['options']
        random.shuffle(options)

        asyncio.create_task(prefetch_explanation_and_next_question())
        return current_question_data, options

    while next_question_data is None:
        await asyncio.sleep(0.1)
    current_question_data = next_question_data
    next_question_data = None
    options = current_question_data['options']
    random.shuffle(options)
    asyncio.create_task(prefetch_explanation_and_next_question())
    return current_question_data, options



def generate_sidebar_content(known_words):
    table_rows = [Tr(Td(word)) for word in known_words]
    return Table(Tbody(*table_rows), cls="sidebar-table")

@rt("/")
async def index():
    global known_words, current_question_data, current_explanation
    question_data, shuffled_options = await get_next_question()

    if question_data is None:
        return Div("Loading...", cls="completed-message")


    due_count, total_vocab_count = get_due_card_fraction(known_words)
    progress_html = P(f"{total_vocab_count} total words", cls="progress")

    question_display = Div(
        Div(question_data["question"], cls="question-text"),
    )

    choice_buttons = []
    for i, option in enumerate(shuffled_options):
        button = Button(
            option,
            hx_post=f"/answer?correct_answer={question_data['answer']}&selected_answer={option}&word={question_data['word_to_review']}",
            hx_target="#explanation",
            cls="choice-btn",
            data_choice=chr(ord('a') + i),
            data_answer=option
        )
        choice_buttons.append(button)

    explanation_div = Div(id="explanation", cls="explanation-area")
    sidebar_content = generate_sidebar_content(known_words)
    sidebar = Div(sidebar_content, id="sidebar", cls="sidebar")

    keyboard_script = Script(_keyboard_script_js())
    style = Style(_style_css())
    zeromd_script = Script(type="module", src="https://cdn.jsdelivr.net/npm/zero-md@3?register")

    return Div(
        style, progress_html, question_display, *choice_buttons,
        explanation_div, sidebar, keyboard_script, zeromd_script,
        cls="main-container"
    )

def _keyboard_script_js():
    return """
        (function() {
            document.body.setAttribute('data-answer-submitted', 'false');
            let sidebarVisible = false;
            const sidebarElement = document.getElementById('sidebar');

            function toggleSidebar() {
                sidebarVisible = !sidebarVisible;
                sidebarElement.style.display = sidebarVisible ? 'block' : 'none';
            }

            function handleKeyPress(event) {
                const answerSubmitted = document.body.getAttribute('data-answer-submitted') === 'true';

                if (event.key.toLowerCase() === 'r') {
                    toggleSidebar();
                    return;
                }

                if (answerSubmitted) {
                    if (event.key === ' ') {
                        event.preventDefault();
                        window.location.href = '/';
                    } else if (event.key.toLowerCase() === 'e') {
                        const selectedAnswer = document.querySelector('.choice-btn.incorrect')?.getAttribute('data-answer');
                        htmx.ajax('GET', `/explain?selected_answer=${selectedAnswer || ''}`, {target: '#explanation'});
                    }
                    return;
                }

                const key = event.key.toLowerCase();
                const choiceMap = {'a': 0, 's': 1, 'd': 2, 'f': 3};
                if (key in choiceMap) {
                    const index = choiceMap[key];
                    const buttons = document.querySelectorAll('.choice-btn');
                    if (buttons[index]) {
                        document.body.setAttribute('data-answer-submitted', 'true');
                        buttons[index].click();
                    }
                }
            }

            document.removeEventListener('keydown', handleKeyPress);
            document.addEventListener('keydown', handleKeyPress);
        })();
    """

def _style_css():
    return """
        body { font-family: sans-serif; display: flex; margin: 0; padding: 20px; background-color: #ffffff; color: #333; overflow-y: scroll; padding-bottom: 0px; }
        .main-container { display: flex; flex-direction: column; align-items: center; justify-content: start; min-height: 100vh; flex-grow: 1; margin-right: 250px; margin-left: auto; margin-right: auto; max-width: 800px; }
        .progress { position: absolute; top: 10px; right: 10px; font-size: 0.9em; color: #777; }
        .question-text { font-size: 1.5em; margin-bottom: 5px; text-align: center; white-space: normal; line-height: 1.5; }
        .translation-text { font-size: 0.9em; color: #555; margin-bottom: 10px; text-align: center; white-space: normal; line-height: 1.4; }
        .choice-btn { padding: 10px 20px; margin: 5px; border: 1px solid #ccc; border-radius: 5px; cursor: pointer; background-color: #f9f9f9; color: #333; min-width: 200px; display: block; margin-left: auto; margin-right: auto; text-align: center; }
        .choice-btn:hover { background-color: #eee; }
        .choice-btn.correct { background-color: #b9f2b9; color: #333; }
        .choice-btn.incorrect { background-color: #f2b9b9; color: #333; }
        .result-area { margin-top: 20px; font-weight: bold; text-align: center; min-height: 30px; color: #333; }
        .explanation-area { margin-top: 5px; padding: 0px 0px; background-color: #fff; border-radius: 5px; max-width: 600px; text-align: left; line-height: 1.6; overflow-wrap: break-word; padding-top: 0; padding-bottom: 0; color: #333; margin-left: auto; margin-right: auto; display: block; }
        .completed-message { font-size: 2em; text-align: center; margin-top: 50px; color: #555; }
        .completed-container { margin-top: 100px; }
        .sidebar { position: fixed; top: 0; right: 0; width: 250px; height: 100%; background-color: #f4f4f4; box-shadow: -2px 0 5px rgba(0,0,0,0.1); overflow-y: auto; display: none; z-index: 1000; padding-top: 0; padding-bottom: 0; margin-bottom: 0; }
        .sidebar-content { padding: 10px; }
        .sidebar-table { width: 100%; border-collapse: collapse; margin-bottom: 0; padding-bottom: 0; }
        .sidebar-table th, .sidebar-table td { padding: 8px; border-bottom: 1px solid #eee; text-align: left; }
        .sidebar-table th { font-weight: bold; }
        .sidebar-table tr:last-child td { border-bottom: none; }
    """

@rt("/answer")
async def answer(correct_answer: str, selected_answer: str, word: str):
    global known_words, current_question_data, current_explanation

    correct = selected_answer == correct_answer

    highlight_script = Script(f"""
        document.querySelectorAll('.choice-btn').forEach(button => {{
            const buttonAnswer = button.getAttribute('data-answer');
            if (buttonAnswer === '{correct_answer}') {{
                button.classList.add('correct');
            }}
            if (!{str(correct).lower()} && buttonAnswer === '{selected_answer}') {{
                button.classList.add('incorrect');
            }}
        }});
    """)

    new_known_words = await update_word_progress_async(word, correct)  # Pass 'correct' for consistency
    known_words[:] = new_known_words
    return Div(highlight_script)

async def update_word_progress_async(word, correct):
    return await asyncio.to_thread(update_word_progress, word, correct, known_words)

@rt("/explain")
async def explain(selected_answer: str = ""):
    global current_question_data, current_explanation
    if current_question_data:
        if current_explanation is None:
          current_explanation = await get_explanation(current_question_data, selected_answer)
        return Div(Zero_md(Script(current_explanation, type="text/markdown")), cls="explanation-area")
    return Div("No question to explain", cls="explanation-area")

serve()
