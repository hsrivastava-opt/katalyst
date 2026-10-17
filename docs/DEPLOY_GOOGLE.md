# Deploying KATALYST to Google Cloud Run

**Status:** Deployment configuration prepared; **not deployed or cloud-tested** in the delivered ZIP.

## Prerequisites

- A Google Cloud project with billing and permission to deploy Cloud Run services.
- Enabled Cloud Run, Artifact Registry, Cloud Build, Firestore, Cloud Storage, and Vertex AI APIs as needed.
- Node 22 and Python 3.12 are used by the Dockerfile stages.
- Google Cloud project region and model are selected based on actual availability and hackathon rules.
- Sample/synthetic data only until the configured sign-in and authorization are verified.

**Foundation update:** Firebase sign-in and server-side ownership checks are now
implemented, but live cloud login/storage and deployment remain unverified.
Follow [FOUNDATION_SETUP.md](FOUNDATION_SETUP.md) first: enable Email/Password and
Google providers, configure authorized domains, web identifiers, ADC/IAM and
Firestore rules. Keep data synthetic until the configured deployment is verified.

## Set project and enable APIs

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com firestore.googleapis.com \
  aiplatform.googleapis.com storage.googleapis.com secretmanager.googleapis.com
```

Create a Firestore (Native) database in Google Cloud Console in an appropriate region. The Firestore adapter uses the default database and collection `katalyst_projects`. Create an isolated non-production project.

## Deploy full frontend + backend container

From the repository root, where the root `Dockerfile` lives:

```bash
gcloud run deploy katalyst-mvp \
  --source . \
  --region YOUR_REGION \
  --set-env-vars KATALYST_AUTH_MODE=firebase,KATALYST_STORE=firestore,KATALYST_AI_PROVIDER=gemini,KATALYST_GEMINI_MODEL=gemini-2.5-flash,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=YOUR_REGION,KATALYST_FIREBASE_WEB_API_KEY=YOUR_PUBLIC_FIREBASE_WEB_KEY,KATALYST_FIREBASE_AUTH_DOMAIN=YOUR_FIREBASE_AUTH_DOMAIN,KATALYST_FIREBASE_WEB_APP_ID=YOUR_FIREBASE_WEB_APP_ID \
  --no-allow-unauthenticated
```

Use a dedicated service account with only required permissions (e.g., Firestore
data access, Firebase user-read for revocation checks, and Vertex AI invocation
when used). The default deny-public invoker setting is deliberate: Cloud Run IAM
is separate from the Firebase ID token the application verifies. An appropriately
authenticated proxy or deliberate invoker configuration is needed for browser
access. Firebase login by itself does not satisfy Cloud Run IAM.

For a public **synthetic-only** hackathon showcase, first implement actual application auth, anti-abuse and quota limits, then configure appropriate invoker policy. Cloud Run IAM authentication for a user browser is not identical to application-level authentication.

If Cloud Run fails during npm build, check Node, package registry connectivity and
builder logs. The offline UI is available only in explicit local demo mode;
Firebase mode requires the React build (or a separately hosted frontend).

## Configure model credentials

Prefer Vertex AI with service-account Application Default Credentials and a permissioned project/region. Alternatively a Developer API key can be supplied through Secret Manager rather than baked into an image.

## Optional Cloud Storage

Set `KATALYST_UPLOAD_BUCKET=your-bucket` to keep original uploads in Google Cloud Storage. This changes upload behavior and requires write permission on the bucket. Without it, the demo stores only extracted, truncated source text in the database; the raw original is not persisted.

## Persistence limits

The prototype stores each whole project document in Firestore for simplicity. Firestore limits document size; keep demo project briefs, document excerpts and audit logs small. A production version should split projects, sources, requirements, events and approvals into distinct documents/collections, enforce per-tenant access, and perform atomic compare-and-swap transactions.

## Security go/no-go

Firebase mode now assigns project owners and audit actors from verified tokens.
Demo identity is fixed, not a user-supplied header, but remains entirely insecure
for public use. Organisational roles, upload scanning, distributed limits, approved
data handling and security-grade append-only audit storage still need production
work. Never deploy `KATALYST_AUTH_MODE=demo` publicly.

## Useful official documentation

- Cloud Run source deployment: https://docs.cloud.google.com/run/docs/deploying-source-code
- Google Gen AI SDK: https://googleapis.github.io/python-genai/
- Google ADK: https://google.github.io/adk-docs/
- Firestore: https://docs.cloud.google.com/firestore/docs
