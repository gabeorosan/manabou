This is a local [fasthtml](https://www.fastht.ml/) web app for mining Japanese vocab using Gemini. It generates Japanese definitions for new vocab words or words from your known vocabulary (randomly), along with incorrect multiple choice options, and gives explanations/translations.

**Demo**
![App Demo](demo.gif)

**How to Run:**

0. **Custom Vocab & Review Ratio:**  
    * replace vocab.txt with your own known vocab words
    * in app.py, change the `REVIEW_TO_NEW_RATIO` from `0.5` to your desired ratio of review to new vocab.  

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
    press a/s/d/f to select an answer, e for Gemini's explanation, r to (review) toggle the sidebar of vocab words, and space to go to the next question.
