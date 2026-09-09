# Streamlit Community Cloud Deployment

This deployment runs the server-friendly application features on Streamlit
Community Cloud. SolidWorks COM extraction remains disabled because Community
Cloud runs Linux; use Quick Selector or enter verified CAD properties manually.

## Security decision

The repository and deployed app must remain private unless ST Engineering
explicitly approves public release. The repository contains vendor-derived
knowledge, engineering workbooks and project evidence.

The project owner must also approve the OpenAI data flow before deployment:

- building the cloud index sends every active knowledge chunk to the OpenAI
  Embeddings API once;
- normal assistant use sends user prompts, tool outputs and retrieved excerpts
  to the OpenAI chat API;
- optional explanatory-image generation sends its controlled visual prompt and
  any user-approved reference image to the OpenAI Image API.

Keeping the Streamlit app private controls who can open the application, but it
does not remove these API data flows.

## Frozen evaluation boundary

Do not change or replace:

- `artifacts/embedding_candidates/bge_m3.json`
- the `eval-freeze-v1` tag
- frozen B/C/D evaluation records

The cloud application uses a separate OpenAI index:

`artifacts/knowledge_embeddings_openai.json`

## GitHub coordinates

- Repository: `qujianyang/CAD-Agent-MPD`
- Branch: `PDF-Ingestion`
- Entrypoint: `app.py`
- Python: `3.10`

## Deploy

1. Open `https://share.streamlit.io` and sign in with the GitHub account that
   administers the repository.
2. Connect Streamlit to private GitHub repositories if it is not already
   authorized.
3. Select **Create app**, then **Yup, I have an app**.
4. Enter the repository, branch and entrypoint listed above.
5. Open **Advanced settings** and select Python 3.10.
6. Paste the contents of `.streamlit/secrets.toml.example` into the Secrets
   field, replacing the placeholder with the approved project OpenAI key.
7. Confirm the OpenAI corpus, prompt and retrieved-excerpt data flow is approved.
8. Deploy and keep the app private.
9. Invite the boss/client by approved email address through the app's Share
   settings.

## Cloud smoke test

After deployment:

1. Open Quick Selector and run the 850 kg, 6-bottom, 4-wall reference case.
2. Confirm the assistant footer reports OpenAI rather than Ollama.
3. Ask: `Why does natural frequency affect transmitted shock?`
4. Confirm the assistant calls `lookup_knowledge` and cites shock-mount sources.
5. Ask for a numerical isolator selection and confirm a deterministic tool call
   appears before the final answer.
6. Open CAD + Shock and confirm it clearly reports that SolidWorks extraction
   is unavailable on Linux.
7. Generate one supplier enquiry pack and download the Word document.
8. Test the explanatory image only if paid Image API use is approved.

## Operational notes

- Streamlit Cloud reads root-level secrets as environment variables.
- GitHub is the deployment source. Pushing to this branch triggers updates.
- Uploaded files and session state are not durable storage.
- Do not place API keys in `.env`, source code, screenshots or Git history.
- If the OpenAI embedding model changes, rebuild the cloud index with the same
  model before changing `OPENAI_EMBEDDING_MODEL`.
