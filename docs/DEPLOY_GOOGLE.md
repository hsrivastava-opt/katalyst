# Deploy KATALYST on Google Cloud Run

The showcase is deployed at
https://katalyst-mvp-861461836467.asia-south1.run.app/.
It uses Firebase Authentication, Firestore, Gemini Developer API, Secret Manager,
Cloud Build, Artifact Registry and Cloud Run. The optional voice pilot connects
directly from the browser to Gemini Live using backend-issued ephemeral tokens.

**Deploy your own copy only to a project you control.** Showcase access does not
grant permission to change the submitter's Google Cloud project. A public GitHub
repository is not automatic Cloud Run deployment: the CI workflow tests/builds,
but source deployment is a separate explicit command.

## Prerequisites

- Google Cloud CLI (`gcloud`) signed in with deployment permissions.
- A billing-enabled Google Cloud project with Firebase added.
- Billing authority and permission to enable APIs, build containers, deploy Cloud
  Run, create service accounts and assign required IAM roles. A build-service-account
  configuration imposed by your organization must also be satisfied.
- Firebase Email/Password and/or Google sign-in enabled and a registered Web app.
- A Firestore Native mode **default database** in your selected region.
- A Gemini Developer API key with selected model access and available quota.
- Local source checkout, Python for the private secret-upload helper, and PowerShell.
  The Cloud Build Docker stages install Node/Python dependencies remotely.

Hosting allowances do not cover all services. Set a budget alert before deployment;
alerts and instance limits are not hard spending caps. Cloud Build, image storage,
network, Firestore, secrets and Gemini can incur charges.

## 1. Select your project and region

Examples below use PowerShell. Replace `YOUR_PROJECT_ID` and the public Firebase
Web app identifiers with values from your own project:

```powershell
$ProjectId = 'YOUR_PROJECT_ID'
$Region = 'asia-south1'
$Service = 'katalyst-mvp'
$Runtime = "katalyst-runtime@$ProjectId.iam.gserviceaccount.com"

gcloud auth login
gcloud config set project $ProjectId
gcloud billing projects describe $ProjectId --format='value(billingEnabled)' --quiet
```

Billing should report `True`. Choose a region near users and preferably the
Firestore database. The showcase uses Mumbai (`asia-south1`).
Do not disable billing on a running Cloud Run project to change Gemini tiers.
A Gemini key may belong to a separate eligible unbilled project; it does not have
to belong to the hosting/Firebase project. Observe Google's quotas and terms.

## 2. Enable APIs and configure Firebase

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iam.googleapis.com firestore.googleapis.com identitytoolkit.googleapis.com firebase.googleapis.com --project=$ProjectId --quiet
```

For a key in this same project, also enable the Gemini Developer API if needed:

```powershell
gcloud services enable generativelanguage.googleapis.com --project=$ProjectId --quiet
```

In Firebase Console:

1. Add Firebase to the project if absent.
2. Enable the desired Authentication providers. Google sign-in needs its support
   email configuration.
3. Register a Web app; record its public `apiKey`, `authDomain` and `appId`.
4. Create the Firestore Native default database if absent; do not replace an
   existing populated database or enable public test rules.
5. Deploy the included deny-all client rules, using an installed Firebase CLI:

```powershell
firebase login
firebase deploy --only firestore:rules --project $ProjectId
```

Browser Firestore operations are intentionally denied. Backend Admin/Cloud
requests use IAM and owner-checked routes, not these browser rules.
See [Firebase setup details](FOUNDATION_SETUP.md#firebase-and-google-cloud-setup).

## 3. Create the runtime identity

For a new project only (reuse a matching existing account rather than recreating it):

```powershell
gcloud iam service-accounts create katalyst-runtime --display-name='KATALYST Cloud Run runtime' --project=$ProjectId --quiet
gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$Runtime" --role=roles/datastore.user --condition=None --quiet --format=none
gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$Runtime" --role=roles/firebaseauth.viewer --condition=None --quiet --format=none
```

The deployer also needs permission to act as the runtime identity. If missing,
ask an administrator to grant `roles/iam.serviceAccountUser` on this service
account to the authorized deployer, not to all users. Do not grant runtime
Owner/Editor or distribute a downloaded service-account key.

Cloud Build's build identity is distinct from the runtime identity. If source
deployment reports build IAM errors, inspect the named principal and follow the
official [source-deployment permissions](https://docs.cloud.google.com/run/docs/deploying-source-code)
for your project's configured build account. Do not repeatedly grant broad roles
or change organization policies to bypass restrictions.

## 4. Store the Gemini key privately

Create the secret container and grant the runtime access to only that secret:

```powershell
gcloud secrets create katalyst-gemini-api-key --replication-policy=automatic --project=$ProjectId --quiet
gcloud secrets add-iam-policy-binding katalyst-gemini-api-key --member="serviceAccount:$Runtime" --role=roles/secretmanager.secretAccessor --project=$ProjectId --quiet --format=none
```

If the secret already exists, skip creation. Add a version with a hidden prompt
from the repository root (use your own installed Python environment):

```powershell
$env:KATALYST_DEPLOY_PROJECT = $ProjectId
$secret = Read-Host 'Gemini API key (hidden)' -AsSecureString
$env:KATALYST_DEPLOY_KEY = (New-Object System.Net.NetworkCredential('', $secret)).Password
Remove-Variable secret
try {
    & .\.venv-live\Scripts\python.exe -c "import os, shutil, subprocess; key=os.environ['KATALYST_DEPLOY_KEY'].strip(); assert key, 'Key is empty'; subprocess.run([shutil.which('gcloud') or 'gcloud', 'secrets', 'versions', 'add', 'katalyst-gemini-api-key', '--data-file=-', '--project='+os.environ['KATALYST_DEPLOY_PROJECT'], '--quiet'], input=key.encode(), check=True)"
} finally {
    Remove-Item Env:\KATALYST_DEPLOY_KEY
    Remove-Item Env:\KATALYST_DEPLOY_PROJECT
}
```

Record the created **version number**, not its value. Creating a new secret
version does not switch an existing service pinned to an older version.

## 5. Core-only deployment (recommended for independent review)

This path requires no Jira, SMTP or voice credentials. It deploys the complete
core workflow with real Firebase, Firestore and Gemini.
Enter only public Web app configuration in this block:

```powershell
$GeminiVersion = '1' # Replace with the version created above.
$PublicKey = 'YOUR_FIREBASE_WEB_API_KEY'
$AuthDomain = 'YOUR_PROJECT_ID.firebaseapp.com'
$AppId = 'YOUR_FIREBASE_WEB_APP_ID'

$envArgs = @(
    'KATALYST_AUTH_MODE=firebase',
    'KATALYST_STORE=firestore',
    'KATALYST_AI_PROVIDER=gemini',
    'KATALYST_GEMINI_MODEL=gemini-3.1-flash-lite',
    'GOOGLE_GENAI_USE_VERTEXAI=false',
    "GOOGLE_CLOUD_PROJECT=$ProjectId",
    "GOOGLE_CLOUD_LOCATION=$Region",
    "KATALYST_FIREBASE_WEB_API_KEY=$PublicKey",
    "KATALYST_FIREBASE_AUTH_DOMAIN=$AuthDomain",
    "KATALYST_FIREBASE_WEB_APP_ID=$AppId",
    'KATALYST_LIVE_ENABLED=false'
) -join ','

gcloud run deploy $Service --source=. --project=$ProjectId --region=$Region "--service-account=$Runtime" "--set-env-vars=$envArgs" "--set-secrets=GOOGLE_API_KEY=katalyst-gemini-api-key:$GeminiVersion" --allow-unauthenticated --ingress=all --min=0 --max=1 --cpu=1 --memory=1Gi --concurrency=4 --timeout=300 --cpu-throttling --quiet
```

Run from the repository root, where the full-stack Dockerfile is located.
`.gcloudignore` incorporates `.gitignore`, excluding local credentials, databases,
virtual environments, generated builds and Git metadata from uploads.
The container builds the frontend and serves both UI/API from one origin.

`--allow-unauthenticated` deliberately allows the browser to load the login page.
**Project APIs still require Firebase authentication and ownership.** Using
Cloud Run IAM-private invocation instead requires a separate authenticated proxy;
Firebase login by itself does not satisfy Cloud Run invoker IAM.
Never deploy `KATALYST_AUTH_MODE=demo` publicly.

The `--set-*` flags replace the relevant configured environment/secret sets.
Use this core-only example for a new service, not to preserve all integrations
on an existing one. For targeted changes use `--update-env-vars` or
`--update-secrets`, preserving unrelated settings.

Model availability/free-tier access is not guaranteed; choose an eligible model.
Cloud Run request-based CPU, zero minimum instances and one maximum instance
reduce idle/scaling costs but do not impose a total cost cap.

## 6. Authorize the hostname and verify

```powershell
$url = gcloud run services describe $Service --project=$ProjectId --region=$Region --format='value(status.url)' --quiet
Invoke-RestMethod -Uri ($url + '/api/health')
```

In Firebase Console -> Authentication -> Settings -> **Authorized domains**,
add the returned hostname **without** `https://` or `/`. If your Firebase browser
key has referrer restrictions, configure the deployed origin appropriately.

Verify in a browser:

1. Homepage loads; `/api/health` reports `ok`.
2. Unauthenticated project requests return 401.
3. Sign-in works and new accounts cannot see other users' projects.
4. One real generation succeeds; inspect `/api/config` for intended provider/model.
5. Save/reload, approvals, prototype actions, SRS/PDF and ZIP work as expected.
6. Do not claim cloud end-to-end acceptance from health checks alone.

## 7. Optional Jira, SMTP and voice

The private environment settings are documented in
[Foundation setup](FOUNDATION_SETUP.md). Integrations are separately gated by
UID allowlists; registration alone does not authorize them.

For the full helper [deploy-cloud.ps1](../deploy-cloud.ps1):

- Configure all required Firebase/Jira/SMTP public/non-secret settings in the
  same PowerShell terminal. The script fails explicitly if they are missing.
- Create secret containers `katalyst-jira-api-token` and `katalyst-smtp-password`.
  Grant runtime secret-accessor permission on each. Upload their values privately
  using the same hidden-prompt/stdin pattern as the Gemini key; never type a token
  into a shell command argument or commit it.
- The helper selects the latest enabled version of each of the **three** secrets
  and pins its number. Confirm which Gemini key project/version you intend to use.
- Runtime identity, APIs, Firestore and Firebase setup must already exist.
- The helper is a deployment tool, not a complete infrastructure bootstrap.

```powershell
.\deploy-cloud.ps1 -ProjectId $ProjectId -Region $Region -Service $Service
```

Its default parameters point to the submitter's showcase project: always override
them for your own deployment. Public runtime settings are passed through a
temporary JSON file removed afterward; private credentials are Secret Manager
references and are not read by the helper.

To enable voice on an already configured service:

```powershell
$VoiceUIDs = 'FIREBASE_UID_1,FIREBASE_UID_2'
$voiceArgs = '^|^KATALYST_LIVE_ENABLED=true|KATALYST_LIVE_MODEL=gemini-3.8-live|KATALYST_LIVE_ALLOWED_UIDS=' + $VoiceUIDs
gcloud run services update $Service --project=$ProjectId --region=$Region "--update-env-vars=$voiceArgs" --quiet
```

The alternate `|` separator preserves commas in the allowlist. Voice reuses the
existing secret-backed `GOOGLE_API_KEY` unless a separate `KATALYST_LIVE_API_KEY`
is deliberately configured. Verify Live availability and pricing first.
Voice requires constrained ephemeral credentials, uses experimental `v1alpha`,
and is read-only. See [voice setup and limits](FOUNDATION_SETUP.md#read-only-live-voice-pilot).

## Updates and troubleshooting

- Adding a secret version alone does not affect a pinned revision. Update it with
  `gcloud run services update ... --update-secrets=GOOGLE_API_KEY=SECRET:VERSION`
  after deliberately selecting the key/version. Never fetch/print secrets to debug.
- Source changes need a new `gcloud run deploy --source=.` build. A GitHub push
  does not automatically update the running app.
- Review Cloud Build/Cloud Run error logs for failed builds/startup, without sharing
  tokens or full environment dumps.
- Cloud Run's runtime has ADC through its service account; do not upload local
  user ADC files or set a local `GOOGLE_APPLICATION_CREDENTIALS` path in the container.
- Health/config routes do not validate Gemini inference, Firestore ownership,
  external delivery or microphone quality; test each feature deliberately.
- Gemini 402 indicates key-project payment/Prepay requirements; 429 indicates
  quota/rate limits. Hosting billing does not grant unlimited/free Gemini calls.
- For optional raw upload archival set `KATALYST_UPLOAD_BUCKET`, enable the Storage
  API and grant bucket-scoped write access. Without it, only bounded extracted
  text is saved, not original uploaded files.
- Firestore stores whole projects; document size and concurrent editing limits
  remain. There is no production collaborative editing or background job queue.

For cleanup, inspect and remove only the specific resources you own and no longer
need, including unused images/build artifacts. Do not delete the project, billing
link, secrets or database as a troubleshooting shortcut.

## Official references

- [Cloud Run source deployment](https://docs.cloud.google.com/run/docs/deploying-source-code)
- [Firebase authorized domains](https://console.firebase.google.com/)
- [Gemini API billing](https://ai.google.dev/gemini-api/docs/billing)
- [Gemini Live ephemeral tokens](https://ai.google.dev/gemini-api/docs/live-api/ephemeral-tokens)
- [Firestore documentation](https://docs.cloud.google.com/firestore/docs)
