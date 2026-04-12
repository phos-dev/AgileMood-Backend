# AgileMood - Claude Onboarding Context

## WHY: Project Purpose
AgileMood is an open-source tool designed to measure and improve psychological safety and emotional awareness in agile software development teams. It collects periodic anonymous feedback, calculates specific metrics (including perception dispersion), and generates dynamic dashboards to help leaders and teams make data-driven interventions.

## WHAT: Project Structure & Tech Stack
The project is structured as a modular web application to allow easy integration into different development environments. 

* **Backend:** A central server providing secure REST APIs, utilizing Node.js or Python Flask.
* **Database:** An OLTP database handling CRUD operations for users, teams, and anonymized mood records.
* **Analysis Module:** Interprets collected metrics, checks for anomalies/dispersion, and generates insights and alerts.
* **Integrations:** Connects with platforms like Slack or Microsoft Teams via webhooks and APIs.

## HOW: Working on AgileMood
To keep this context focused, specific technical instructions are separated into focused documents. Before starting a task, please review the relevant documentation in the `agent_docs/` folder:

* **Architecture & APIs:** Read `agent_docs/backend_architecture.md` for endpoint structures, auth flow (SSO/OIDC/RBAC), and database schemas.
* **Frontend Components:** Read `agent_docs/frontend_state.md` for UI guidelines and state management.
* **Testing & Verification:** Read `agent_docs/running_tests.md` for instructions on running the test suites to verify your changes.
* **Linting:** Do not manually format code. Run the project's automated linters and formatters as defined in `agent_docs/code_conventions.md`.