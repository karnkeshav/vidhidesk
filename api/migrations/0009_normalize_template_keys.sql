-- VidhiDesk — Migration 0009: Normalize template_key format across all templates to kebab-case
-- Ensures all template_key values in the templates table strictly adhere to the kebab-case standard (e.g. 'service-agreement').
-- Idempotent: safe to re-run.

update templates
set template_key = 'service-agreement'
where template_key = 'service_agreement' or name = 'Service Agreement';
