"""Flask CLI and development entry point."""

from bizpilot import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

