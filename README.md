This is a local [fasthtml](https://www.fastht.ml/) web app for mining Japanese vocab using Gemini. It generates Japanese definitions for vocab words from a given list based on your ELO, along with incorrect multiple choice options, and gives explanations/translations. Vocab list is parsed form of these [15000 words](https://github.com/hingston/japanese/blob/master/15000-japanese-words.txt); can be substituted with anything.

**Demo**
![App Demo](demo.gif)

**How to Run:**

0. **Custom Vocab**  
    * replace vocab.txt with your own known vocab words

1.  **Install Dependencies:**
    ```bash
    pip install fasthtml google-generativeai python-dotenv
    ```

2.  **Set up API Key:**
    *   Get a Google Gemini API key.
    *   Create a `.env` file.
    *   Add to `.env`:
        ```
        GEMINI_API_KEY=your_api_key_here
        ```
3.  **Run:**
    ```bash
    python app.py
    ```
    Open your browser to the address provided (usually `http://localhost:5001`).

4. **Usage:**  
    press a/s/d/f to select an answer, e for Gemini's explanation, and space to go to the next question.
