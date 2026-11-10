# Initial spec

## General description

Theme: Project management/profiles dashboard - a service to  create, update, share, and delete projects information (details, attached documents)

## Stack

- Python 3.12+
- FastAPI
- PostgreSQL + Optional ORM (SQLAlchemy, etc)
- Docker
- AWSS3 (file storage)
- AWS Lambda functions (for image processing , size calculations on s3 event)
- CI/CD:  GitHub Actions/Gitlab CI (testing/linting/building/pushing to registry/deploy to cloud on merge request)

## Desired functionality

- User login/auth
- Create/Delete projects
- Add/Update project’s info/details - name, description
- Add/Update/Remove projects documents (docx, pdf)
- Share project with other users to access

## API

- `POST /auth` - Create user (login, password, repeat password)
- `POST /login` - Login into service (login, password)
- `POST /projects` - Create project from details (name, description). Automatically gives access to created project to user, making him the owner (admin of the project).
- `GET /projects` - Get all projects, accessible for a user. Returns list of projects full info(details + documents).
- `GET /project/<project_id>/info` - Return project’s details, if user has access
- `PUT /project/<project_id>/info` - Update projects details - name, description. Returns the updated project’s info
- `DELETE /project/<project_id>` - Delete project, can only be performed by the projects’ owner. Deletes the corresponding  documents
- `GET /project/<project_id>/documents` - Return all of the project's documents
- `POST /project/<project_id>/documents` - Upload document/documents for a specific project
- `GET /document/<document_id>` - Download document, if the user has access to the corresponding project
- `PUT /document/<document_id>` - Update document
- `DELETE /document/<document_id>` - Delete document and remove it from the corresponding project
- `POST /project/<project_id>/invite?user=<login>` - Grant access to the project for a specific user. If the request is not coming from the owner of the project, results in error. Granting access gives participant permissions to receiving user

### Optional

- `GET /project/<project_id>/share?with=<email>` - send a `GET /join` link with correct hashed token for the requested project to specified email, that can be opened by a different user in a browser

## Phase 2 Additional Tasks

- Normalization + denormalization of db tables
- Creation of db with and without ORM
- S3+Lambda: Image resize(optional), calculation of sum of project file's size and apply limit
- Tests, CI&CD bindings
- package creation , CI&CD bindings , implementation of related tools (pyproject.toml, tox || poetry)
- validate all data with pydantic
- All the business logic requests should be authorized via JWT (including resolving access permissions), issued by POST /login. JWT should last 1 hour.

## Implementation notes

1. All the returned data must be in JSON format (except for file data) + proper http status codes
2. 2 types of access – owner (creator of the project, can do anything) and participant (user invited to the project, can modify, cannot delete)
3. Exact API parameters/endpoints can be changed/updated upon agreement with the mentor, as long as they cover the described logic
