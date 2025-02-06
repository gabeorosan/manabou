This is a local [fasthtml](https://www.fastht.ml/) web app for mining Japanese vocab using Gemini. It generates a new vocab word, its Japanese definition and other incorrect multiple choice options, and gives explanations/translations.

**Demo**
![App Demo](demo.gif)

**How to Run:**

0. **vocab list**
    replace vocab.txt with your own known vocab words

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

4. **usage**
    press a/s/d/f to select an answer, e for Gemini's explanation, r to (review) toggle the sidebar of vocab words, and space to go to the next question.
