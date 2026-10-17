# Scope control and next steps

## Deliberately not implemented in this hackathon artifact

- Google Stitch API integration and automatic conversion of Stitch output into executing components.
- Document AI OCR, live microphone transcription, video/speaker diarization and meeting intelligence.
- Vector RAG over multiple enterprise knowledge sources; citations are source references in a small demo dataset.
- Full fourteen-agent organization and ADK Agent Runtime deployment (only a short-lived ADK stage-agent adapter is provided).
- Arbitrary code generation, GitHub pull requests, CI/CD pipelines, and a complete SDLC lifecycle.
- SSO/SAML/SCIM, organisation/role permissions, comprehensive privacy controls,
  distributed rate limits and cloud-verified identity. Firebase per-user
  authentication/ownership is now implemented in the foundation milestone.
- Multi-region availability, 500 concurrent users, security certification, penetration testing and load testing.
- Accessibility certification, visual design-system validation, stakeholder research and real KPI benchmarking.

## Recommended next milestones

1. **Google proof:** test real Gemini responses and ADK mode end-to-end with two test briefs. Add automated evaluation of schema validity and traceability.
2. **Render quality:** expand the safe UI schema with tables, navigation routes, forms, conditional validations, required fields, and domain-specific event types. Keep generated content and executable code separate.
3. **Identity hardening:** verify the implemented Firebase login and ownership
   against real cloud services, then add role-based approvals, organisation
   tenancy, distributed abuse controls and immutable audit storage.
4. **Data:** normalize Firestore schema, manage document source permissions, connect Google Drive and Agent Search for grounded retrieval.
5. **Prototype pipeline:** evaluate Stitch capabilities and export terms, add trusted React code scaffolds only after safe generation and sandboxing are designed.
6. **Benchmarks:** compare manual versus KATALYST requirements-to-prototype cycle times using a fixed set of representative tasks.
7. **Production:** add concurrency control, retry policies, rate limits, secrets, deployment automation, comprehensive error handling and observability.

## Engineering decision

The new product specification is being implemented incrementally, starting with
the existing stack's [application foundation](FOUNDATION_SETUP.md). The SRS,
Gmail, UI/UX/Stitch, architecture and Jira stages remain separate future milestones.

The earliest differentiator to prove is reliable **brief → approved stories → working three-screen prototype**. Do not increase agent count or integrations until that journey succeeds with a live Google model and three independent inputs.
