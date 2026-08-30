"""Executive Health AI V0.1 data foundation."""

from executive_health_ai.config import load_project_environment

# Load the Git-ignored project-local configuration before database, API, or
# Streamlit modules read settings. Explicit shell variables still win.
load_project_environment()
