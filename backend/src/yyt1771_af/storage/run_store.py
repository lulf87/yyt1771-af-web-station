from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from yyt1771_af.core.models import MeasurementDefinition, RunSample


class RunArtifactStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        if self._root is not None:
            return self._root
        return Path(os.environ.get("YYT1771_AF_RUNS_DIR", "runs"))

    def create_run_dir(self, run_id: str) -> Path:
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir

    def write_metadata(self, run_id: str, metadata: dict[str, Any]) -> None:
        self._write_json(run_id, "metadata.json", metadata)

    def write_measurement_definition(
        self,
        run_id: str,
        measurement_definition: MeasurementDefinition,
    ) -> None:
        self._write_json(
            run_id,
            "measurement_definition.json",
            measurement_definition.model_dump(mode="json"),
        )

    def append_sample(self, sample: RunSample) -> None:
        samples_path = self.root / sample.run_id / "samples.jsonl"
        line = json.dumps(sample.model_dump(mode="json"), separators=(",", ":"))
        with samples_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def read_samples(self, run_id: str) -> list[dict[str, Any]]:
        samples_path = self.root / run_id / "samples.jsonl"
        if not samples_path.exists():
            return []
        return [
            json.loads(line)
            for line in samples_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def read_metadata(self, run_id: str) -> dict[str, Any] | None:
        metadata_path = self.root / run_id / "metadata.json"
        if not metadata_path.exists():
            return None
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def read_measurement_definition(self, run_id: str) -> dict[str, Any] | None:
        definition_path = self.root / run_id / "measurement_definition.json"
        if not definition_path.exists():
            return None
        return json.loads(definition_path.read_text(encoding="utf-8"))

    def write_analysis(self, run_id: str, analysis: dict[str, Any]) -> None:
        self._write_json(run_id, "analysis.json", analysis)

    def read_analysis(self, run_id: str) -> dict[str, Any] | None:
        analysis_path = self.root / run_id / "analysis.json"
        if not analysis_path.exists():
            return None
        return json.loads(analysis_path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []

        runs: list[dict[str, Any]] = []
        for run_dir in sorted(self.root.iterdir()):
            if not run_dir.is_dir():
                continue
            metadata_path = run_dir / "metadata.json"
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            else:
                metadata = {"run_id": run_dir.name}
            metadata.setdefault("run_id", run_dir.name)
            runs.append(metadata)
        return runs

    def _write_json(self, run_id: str, filename: str, payload: dict[str, Any]) -> None:
        path = self.root / run_id / filename
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )


run_artifact_store = RunArtifactStore()
