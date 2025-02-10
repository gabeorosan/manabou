from fasthtml.common import *
import random
import re
from pathlib import Path
import google.generativeai as genai
import os
import time
from fasthtml.components import Zero_md, HTML, RawHTML
import asyncio
import numpy as np

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")
app, rt = fast_app()

VOCAB_FILE = "vocab.txt"
PROGRESS_FILE = "progress.txt"

async def get_explanation(question_data, selected_answer=None):
    is_correct_bool = selected_answer == question_data['answer'] if selected_answer else True
    prompt_text = f"""
    Given the following japanese definition, and words:
    Definition: {question_data['question']}
    Words: {question_data['options']}
    Format your output as follows, with no other text, and no romaji:
    Translation: [English translation of the definition]
    
    1. [Word 1] ([Furigana for Word 1]) - [English translation of Word 1]
    2. [Word 2] ([Furigana for Word 2]) - [English translation of Word 2]
    3. [Word 3] ([Furigana for Word 3]) - [English translation of Word 3]
    4. [Word 4] ([Furigana for Word 4]) - [English translation of Word 4]

    [Concise one-line explanation of the correct answer]\n
    """
    if not is_correct_bool and selected_answer:
        prompt_text += f"[Concise one-line explanation of why '{selected_answer}' is incorrect]"
    print("get_explanation - Prompt:\n", prompt_text)
    for attempt in range(10):
        try:
            response = await model.generate_content_async(prompt_text)
            explanation = response.text.strip().replace("Translation: ", "")
            print("get_explanation - Explanation generated:", explanation)
            return explanation
        except Exception as e:
            print(f"Explanation generation failed with model {model}, attempt {attempt + 1}: {e}")
            if attempt < 9:
                await asyncio.sleep(5)
    print("get_explanation - Failed to generate explanation.")
    return "Sorry, couldn't generate explanation."

async def generate_question_gemini(known_words, mean, variance):
    print(f"generate_question_gemini - Called with mean: {mean}, variance: {variance}")
    return await generate_known_word_question(known_words, mean, variance)

async def generate_known_word_question(known_words, mean, variance):
    if not known_words:
        print("generate_known_word_question - No known words.")
        return None
    lower_bound = max(0, int(mean - variance))
    upper_bound = min(len(known_words), int(mean + variance))
    print(f"generate_known_word_question - Lower bound: {lower_bound}, Upper bound: {upper_bound}")
    if lower_bound >= upper_bound:
       lower_bound = max(0, upper_bound-1)
       print(f"generate_known_word_question - Bounds adjusted. Lower: {lower_bound}, Upper: {upper_bound}")
    target_word_index = random.randint(lower_bound, upper_bound -1)
    target_word = known_words[target_word_index]
    print(f"generate_known_word_question - Target word: {target_word}, Index: {target_word_index}")
    prompt = f"""
Write a Japanese definition for the word {target_word} to use as a multiple choice question, and choose three other words to use as incorrect multiple choice options. Put the hiragana for the full definition on the line after it. To make the answer unambiguous, choose the incorrect options so that they do not fit the definition. Put the correct answer as option number 1. Do not put furigana or romaji.

Format the output as follows, with no other text:
Definition: [Japanese definition]
Hiragana: [Hiragana for Japanese definition]
1) [correct option]
2) [incorrect option]
3) [incorrect option]
4) [incorrect option]
"""
    print("generate_known_word_question - Prompt:\n", prompt)
    for attempt in range(10):
        try:
            response = await model.generate_content_async(prompt)
            response_text = response.text.strip()
            print(f"Gemini Known Word Output (Attempt {attempt + 1}):\n{response_text}")
            question_data = {}
            lines = response_text.strip().split('\n')
            lines = [line for line in lines if line.strip()]
            if len(lines) < 6:
                print(f"Parsing failed with model {model}, attempt {attempt + 1}")
                continue
            question_data["question"] = lines[0].split(': ', 1)[1].strip()
            question_data["hiragana"] = lines[1].split(': ', 1)[1].strip()
            options_list = [line.split(') ', 1)[1].strip() for line in lines[2:6]]
            question_data["options"] = options_list
            question_data["answer"] = options_list[0]
            question_data["word_index"] = target_word_index  # Store the index
            print("generate_known_word_question - Question data:", question_data)
            return question_data
        except Exception as e:
            print(f"Request Error (Attempt {attempt + 1}): {e}")
            print(f"Question generation failed with model {model}, attempt {attempt+1}: {e}")
        if attempt < 9:
            await asyncio.sleep(5)
    print("generate_known_word_question - Failed to generate question.")
    return None

def load_word_progress():
    path = Path(VOCAB_FILE)
    if path.exists():
        words = path.read_text().splitlines()
        print(f"load_word_progress - Loaded {len(words)} words.")
        return words
    else:
        print("load_word_progress - No vocab file found.")
        return []

def update_word_progress(word_index, correct, known_words, mean, variance):
    print(f"update_word_progress - Correct: {correct}, Index: {word_index}")
    if correct:
        mean = min(len(known_words) - variance, mean + 100)
        print(f"update_word_progress - Answer correct, increasing mean to: {mean}")
    else:
        mean = max(variance, mean-1000)
        print(f"update_word_progress - Answer incorrect, decreasing mean to: {mean}")
    return mean, variance

def load_progress():
    try:
        with open(PROGRESS_FILE, "r") as f:
            mean, variance = map(float, f.readline().split())
            print(f"load_progress - Loaded mean: {mean}, variance: {variance}")
            return mean, variance
    except (FileNotFoundError, ValueError):
        print("load_progress - Initializing progress.")
        mean = len(known_words) // 2 if known_words else 0
        variance = 1000
        return mean, variance

def save_progress(mean, variance):
    with open(PROGRESS_FILE, "w") as f:
        f.write(f"{mean} {variance}")
    print(f"save_progress - Saved mean: {mean}, variance: {variance}")

def get_due_card_fraction(known_words):
    return 0, len(known_words)

known_words = load_word_progress()
next_question_data = None
current_question_data = None
current_explanation = None
prefetch_lock = asyncio.Lock()
mean, variance = load_progress()

async def prefetch_next_question():
    global next_question_data, known_words, prefetch_lock, mean, variance
    async with prefetch_lock:
        print("prefetch_next_question - Starting.")
        if next_question_data is None:
            question_data = await generate_question_gemini(known_words, mean, variance)
            if question_data:
                question_data['word_to_review'] = question_data['answer']
                next_question_data = question_data
                print("prefetch_next_question - Prefetched question data.")
            else:
                print("prefetch_next_question - Failed to prefetch question data.")

async def prefetch_explanation_and_next_question():
    global current_question_data, current_explanation, next_question_data, known_words, prefetch_lock, mean, variance
    async with prefetch_lock:
        print("prefetch_explanation_and_next_question - Starting.")
        if current_question_data:
            current_explanation = await get_explanation(current_question_data)
        question_data = await generate_question_gemini(known_words, mean, variance)
        if question_data:
            question_data['word_to_review'] = question_data['answer']
            next_question_data = question_data
            print("prefetch_explanation_and_next_question - Prefetched question and explanation.")
        else:
            print("prefetch_explanation_and_next_question - Failed to prefetch question.")

async def get_next_question():
    global next_question_data, current_question_data, current_explanation, mean, variance
    print("get_next_question - Starting.")
    if current_question_data is None:
        question_data = await generate_question_gemini(known_words, mean, variance)
        if question_data:
              question_data['word_to_review'] = question_data['answer']
              current_question_data = question_data
              print("get_next_question - Got initial question data.")
        else:
            print("get_next_question - Failed to get initial question.")
            return None, None
        options = current_question_data['options']
        random.shuffle(options)
        asyncio.create_task(prefetch_explanation_and_next_question())
        return current_question_data, options
    while next_question_data is None:
        print("get_next_question - Waiting for next question data.")
        await asyncio.sleep(0.1)
    current_question_data = next_question_data
    next_question_data = None
    options = current_question_data['options']
    random.shuffle(options)
    print("get_next_question - Got next question data.")
    asyncio.create_task(prefetch_explanation_and_next_question())
    return current_question_data, options

@rt("/")
async def index():
    global known_words, current_question_data, current_explanation, mean, variance
    print("index - Starting.")
    question_data, shuffled_options = await get_next_question()
    if question_data is None:
        print("index - No question data available.")
        return Div("Loading...", cls="completed-message")
    word_index = question_data['word_index'] if question_data else 0
    due_count, total_vocab_count = get_due_card_fraction(known_words)
    progress_html = P(f"{word_index+1}/{total_vocab_count}", cls="progress")
    mean_html =  P(f"{int(np.round(mean))} 位", cls="progress", style="margin-top: 20px;")
    question_lines = question_data["question"].splitlines()
    hiragana_lines = question_data["hiragana"].splitlines()
    combined_lines = []
    for i in range(max(len(question_lines), len(hiragana_lines))):
        if i < len(hiragana_lines):
            combined_lines.append(Div(hiragana_lines[i], cls="hiragana-text"))
        if i < len(question_lines):
            combined_lines.append(Div(question_lines[i], cls="question-text"))
    question_display = Div(*combined_lines, cls="question-container")
    choice_buttons = []
    for i, option in enumerate(shuffled_options):
        button = Button(
            option,
            hx_post=f"/answer?correct_answer={question_data['answer']}&selected_answer={option}&word_index={word_index}",
            hx_target="#explanation",
            cls="choice-btn",
            data_choice=chr(ord('a') + i),
            data_answer=option
        )
        choice_buttons.append(button)
    explanation_div = Div(id="explanation", cls="explanation-area")
    keyboard_script = Script(_keyboard_script_js())
    style = Style(_style_css())
    zeromd_script = Script(type="module", src="https://cdn.jsdelivr.net/npm/zero-md@3?register")
    print("index - Returning main page.")
    return Div(
        style, progress_html, mean_html, question_display, *choice_buttons,
        explanation_div, keyboard_script, zeromd_script,
        cls="main-container"
    )

def _keyboard_script_js():
    return """
        (function() {
            document.body.setAttribute('data-answer-submitted', 'false');
            function handleKeyPress(event) {
                const answerSubmitted = document.body.getAttribute('data-answer-submitted') === 'true';
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
        .main-container { display: flex; flex-direction: column; align-items: center; justify-content: start; min-height: 100vh; flex-grow: 1; margin-left: auto; margin-right: auto; max-width: 800px; }
        .progress { position: absolute; top: 10px; right: 10px; font-size: 0.9em; color: #777; }
        .question-container { display: flex; flex-direction: column; align-items: center; margin-bottom: 10px; }
        .question-text { font-size: 1.5em; text-align: center; white-space: normal; line-height: 1.5; }
        .hiragana-text { font-size: 1.2em; color: #555; text-align: center; margin-bottom: 0px; }
        .translation-text { font-size: 0.9em; color: #555; margin-bottom: 10px; text-align: center; white-space: normal; line-height: 1.4; }
        .choice-btn { padding: 10px 20px; margin: 5px; border: 1px solid #ccc; border-radius: 5px; cursor: pointer; background-color: #f9f9f9; color: #333; min-width: 200px; display: block; margin-left: auto; margin-right: auto; text-align: center; }
        .choice-btn:hover { background-color: #eee; }
        .choice-btn.correct { background-color: #b9f2b9; color: #333; }
        .choice-btn.incorrect { background-color: #f2b9b9; color: #333; }
        .result-area { margin-top: 20px; font-weight: bold; text-align: center; min-height: 30px; color: #333; }
        .explanation-area { margin-top: 5px; padding: 0px 0px; background-color: #fff; border-radius: 5px; max-width: 600px; text-align: left; line-height: 1.6; overflow-wrap: break-word; padding-top: 0; padding-bottom: 0; color: #333; margin-left: auto; margin-right: auto; display: block; }
        .completed-message { font-size: 2em; text-align: center; margin-top: 50px; color: #555; }
        .completed-container { margin-top: 100px; }
    """

@rt("/answer")
async def answer(correct_answer: str, selected_answer: str, word_index: int):
    global known_words, current_question_data, current_explanation, mean, variance
    print(f"answer - Correct answer: {correct_answer}, Selected answer: {selected_answer}, Word Index: {word_index}")
    correct = selected_answer == correct_answer
    mean, variance = update_word_progress(word_index, correct, known_words, mean, variance)
    save_progress(mean, variance)
    print(f"answer - Updated mean: {mean}, variance: {variance}")
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
    print("answer - Returning button highlight script.")
    return Div(highlight_script)

@rt("/explain")
async def explain(selected_answer: str = ""):
    global current_question_data, current_explanation
    print(f"explain - Selected answer: {selected_answer}")
    if current_question_data:
        if current_explanation is None:
          current_explanation = await get_explanation(current_question_data, selected_answer)
        print("explain - Returning explanation.")
        return Div(Zero_md(Script(current_explanation, type="text/markdown")), cls="explanation-area")
    print("explain - No question to explain.")
    return Div("No question to explain", cls="explanation-area")

serve()
