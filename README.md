# Split Screen Application

A Django application featuring a split-screen interface with a result display and chat interface. The application uses modern frontend tooling with Vite and Tailwind CSS.

## Project Structure

```
application/
├── app/
│   ├── frontend/           # Frontend assets and configuration
│   │   ├── src/
│   │   │   ├── css/
│   │   │   │   └── main.css    # Tailwind CSS imports
│   │   │   └── main.js         # JavaScript entry point
│   │   ├── vite.config.js      # Vite configuration
│   │   ├── tailwind.config.js  # Tailwind configuration
│   │   ├── postcss.config.js   # PostCSS configuration
│   │   └── package.json        # NPM dependencies
│   ├── templates/         # Django templates
│   │   ├── base.html     # Base template with split-screen layout
│   │   └── home.html     # Home page template
│   ├── static/           # Static files
│   │   └── images/       # Image assets
│   └── app/             # Django project configuration
│       ├── settings.py   # Django settings
│       ├── urls.py       # URL configuration
│       └── views.py      # View functions
```

## Prerequisites

- Python 3.x
- Node.js and npm
- Django
- Vite
- Tailwind CSS

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd application
   ```

2. Install Python dependencies using Pipenv:
   ```bash
   cd app
   pipenv install
   pipenv shell  # Activate the virtual environment
   ```

3. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

## Running the Application

The application requires running both the Django backend server and the Vite development server.

1. Start the Vite development server:
   ```bash
   cd app/frontend
   npm run dev
   ```
   This will start the Vite server on http://localhost:5173

2. In a separate terminal, start the Django development server:
   ```bash
   cd app
   python manage.py runserver
   ```
   This will start the Django server on http://localhost:8000

3. Visit http://localhost:8000 in your browser to see the application

## Development

### Frontend Development
- The frontend code is located in the `app/frontend` directory
- Vite handles JavaScript bundling and provides hot module replacement
- Tailwind CSS is used for styling
- Edit `src/main.js` for JavaScript changes
- Edit `src/css/main.css` for custom CSS (Tailwind is already imported)

### Backend Development
- Django views are in `app/app/views.py`
- Templates are in `app/templates/`
- URL routing is configured in `app/app/urls.py`

### Building for Production

To build the frontend assets for production:

```bash
cd app/frontend
npm run build
```

This will create optimized assets in the `app/static/dist` directory, which Django will serve in production.
