# Match Scraper Web App

This web application scrapes a website for live and upcoming match data and displays it in a user-friendly interface.

## Local Development

1.  **Create a virtual environment and install dependencies:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

2.  **Run the Flask development server:**

    ```bash
    python app.py
    ```

    The application will be available at [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

## Deployment to Render

This project is ready to be deployed to Render.

1.  **Create a new Web Service on Render:**
    *   Go to the [Render Dashboard](https://dashboard.render.com/) and click "New +" -> "Web Service".
    *   Connect your GitHub or GitLab repository where you have pushed this project.

2.  **Configure the Web Service:**
    *   **Name:** Give your service a name (e.g., `match-scraper`).
    *   **Region:** Choose a region close to you.
    *   **Branch:** Choose the branch you want to deploy (e.g., `main`).
    *   **Root Directory:** Leave this as is, unless you have placed the code in a subdirectory.
    *   **Runtime:** Render should automatically detect `Python`.
    *   **Build Command:** `pip install -r requirements.txt`
    *   **Start Command:** `gunicorn app:app`

3.  **Click "Create Web Service".**

Render will automatically build and deploy your application. Once the deployment is complete, you will be given a URL where you can access your live application.# match
