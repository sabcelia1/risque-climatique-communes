#!/usr/bin/env bash
# Configuration Google Cloud SANS CLÉ pour GitHub Actions (Workload Identity Federation).
# À coller dans Cloud Shell (icône >_ en haut de la console Google Cloud).
# Le script peut être relancé sans risque : ce qui existe déjà est conservé.
set -euo pipefail

PROJECT_ID="risques-climatiuqes-communes"
REPO="sabcelia1/risque-climatique-communes"
SA_NAME="pipeline-risque"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
POOL="github"
PROVIDER="github-repo"

gcloud config set project "$PROJECT_ID" --quiet
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

echo "1/5 Activation des API..."
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com bigquery.googleapis.com --quiet

echo "2/5 Compte de service..."
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name="Pipeline risque climatique"

echo "3/5 Droits BigQuery du compte de service..."
for ROLE in roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
    --role="$ROLE" --condition=None --quiet >/dev/null
done

echo "4/5 Fédération d'identité GitHub (limitée à ce seul dépôt)..."
gcloud iam workload-identity-pools describe "$POOL" --location=global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "$POOL" --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe "$PROVIDER" --location=global \
  --workload-identity-pool="$POOL" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location=global \
    --workload-identity-pool="$POOL" --display-name="Depot risque climatique" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='${REPO}'"

echo "5/5 Autorisation du dépôt GitHub à agir en tant que compte de service..."
gcloud iam service-accounts add-iam-policy-binding "$SA" --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}" \
  --quiet >/dev/null

echo
echo "Terminé. Valeur à copier :"
echo "GCP_WIF_PROVIDER: projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
