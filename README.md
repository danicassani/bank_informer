# bank_informer
An application that helps me process my bank extracts and show insights about the movements in a web page.

## Development setup

1. Create and activate a virtual environment with Python 3.12 or newer.
2. Install the project dependencies:
   ```bash
   pip install "Django>=5.0,<6.0"
   ```
   If your environment sits behind a proxy that blocks external downloads, you will need to provide the wheel files manually or install them from a local package index.
3. Apply the database migrations:
   ```bash
   python manage.py migrate
   ```
4. Run the development server:
   ```bash
   python manage.py runserver
   ```

## Running tests

Execute the Django test suite with:

```bash
python manage.py test
```

> **Note:** In locked-down environments (such as this execution sandbox) direct `pip install` calls may fail with proxy errors, which prevents the test command from running until Django is installed through another channel.
