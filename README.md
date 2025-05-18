# Split Screen Application

A Django application featuring a split-screen interface with a result display and chat interface. The application uses modern frontend tooling with Tailwind CSS.

## Project Structure

```
application/
├── static/
│   ├── src/
│   │   └── main.css      # Tailwind CSS source
│   └── dist/
│       └── main.css      # Compiled CSS output
├── templates/            # Django templates
│   ├── base.html         # Base template with split-screen layout
│   └── home.html         # Home page template
├── app/                  # Django project configuration
│   ├── settings.py       # Django settings
│   ├── urls.py           # URL configuration
│   └── views.py          # View functions
├── package.json          # NPM dependencies
├── tailwind.config.js    # Tailwind configuration
└── postcss.config.js     # PostCSS configuration
```

## Prerequisites

- Python 3.x
- Node.js and npm
- Django
- Tailwind CSS

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd application
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install frontend dependencies:
   ```bash
   npm install
   ```

## Running the Application

1. Start the Tailwind CSS watcher:
   ```bash
   npm run watch
   ```
   This will watch for changes in your CSS and compile them automatically

2. In a separate terminal, start the Django development server:
   ```bash
   python manage.py runserver
   ```
   This will start the Django server on http://localhost:8000

3. Visit http://localhost:8000 in your browser to see the application

## Development

### Frontend Development
- Tailwind CSS is used for styling
- Edit `static/src/main.css` for custom CSS
- The CSS is automatically compiled to `static/dist/main.css`
- Tailwind's utility classes can be used directly in your HTML templates

### Backend Development
- Django views are in `app/app/views.py`
- Templates are in `app/templates/`
- URL routing is configured in `app/app/urls.py`

### Building for Production

To build the CSS for production:

```bash
npm run build
```

This will create an optimized CSS file in the `static/dist` directory, which Django will serve in production.
