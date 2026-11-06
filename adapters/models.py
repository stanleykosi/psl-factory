from typing import Protocol

class EvidenceProvider(Protocol):
    name: str
    def extract(self, text: str) -> dict: ...

class SyntheticEvidenceProvider:
    name = 'synthetic-extractive-v1'
    def extract(self, text):
        return {'facts': [{'quote': line.strip()} for line in text.splitlines() if line.strip()][:8],
                'uncertainties': ['Synthetic extraction; human interpretation required'], 'proposed_actions': []}
