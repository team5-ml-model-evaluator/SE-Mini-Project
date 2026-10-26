
#!/usr/bin/env python
"""Command-line utility for Django administrative tasks."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django could not be imported. Install the dependencies "
            "from requirements.txt before running this command."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
