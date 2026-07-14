# SEIB-2026 dataset card

SEIB-2026 is a deterministic synthetic benchmark for multi-hop enterprise identity and authorization research. It is not sampled from customer tenants and contains no real credentials, personal data, or measured breach events.

Profiles model a SaaS scale-up, a regulated financial organization, and a global hybrid enterprise. Small, medium, and large targets are defined in code; each seed creates a coherent clean graph and paired low-risk, mixed-risk, and truth-remediated variants. Twelve scenario families include transitive groups, role chains, workload identities, CI/CD paths, federation, dormant/external identities, provider-specific paths, and hard negatives. Generation emits validation, distribution, coherence, checksum, and dataset-card artifacts.

Truth paths and scenario tables are physically separated from inference inputs. The benchmark supports controlled comparisons and regression tests, not claims of population representativeness. Scenario injection necessarily favors modeled families. Generated data may be redistributed under Apache-2.0 with its manifest and this warning intact.
