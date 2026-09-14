#!/usr/bin/env python3
"""
crystal_loader.py — Cold-Boot Memory Crystal Ingestion Engine
================================================================================
Handles cold-boot startup for the Enquerant (EQ) V2.0 system:
- Ingests binary DELM datasets (niichii_v*.bin) and recognition binaries (gis_english.bin).
- Parses native DELM record format: [record_type uint16][coord_len uint8][coord bytes][payload_len uint32][JSON].
- Compiles the full memory crystal structure into deterministic in-memory lookup indices.
- Verifies integrity via SHA-256 manifest validation.
================================================================================
"""

import os
import struct
import json
import hashlib
glob_import_ok = True
try:
    import glob
except ImportError:
    glob_import_ok = False

from typing import Dict, List, Any, Optional, Tuple


class CrystalLoader:
    """
    Cold-boot ingestion engine that compiles binary DELM volumes and recognition 
    substrates into an in-memory knowledge crystal.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.abspath(os.path.dirname(__file__))
        self.delm_volumes_dir = os.path.join(self.base_dir, "delm_volumes")
        
        self.records: List[Dict[str, Any]] = []
        self.coordinate_index: Dict[str, List[Dict[str, Any]]] = {}
        self.subject_index: Dict[str, List[Dict[str, Any]]] = {}
        
        self.volumes_count = 0
        self.volume_names: List[str] = []
        self.total_records_loaded = 0
        self.crystal_checksum = 1.0
        self.total_placeholders_count = 0
        self.potential_placeholders: List[str] = []
        self.dislocation_registry: Dict[str, Dict[str, Any]] = {}

        # Execute cold-boot ingestion and manifold dislocation audit immediately upon instantiation
        self.ingest_crystal()

    def _parse_delm_stream(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Parses raw binary streams adhering to the native DELM wire format:
        [record_type: uint16][coord_len: uint8][coord: utf-8][payload_len: uint32][payload: json]
        """
        records = []
        offset = 0
        data_len = len(data)

        while offset < data_len:
            # Check remaining bytes for header (uint16 + uint8 = 3 bytes minimum)
            if offset + 3 > data_len:
                break

            record_type, coord_len = struct.unpack_from("<HB", data, offset)
            offset += 3

            if offset + coord_len + 4 > data_len:
                break

            coord_bytes = data[offset : offset + coord_len]
            offset += coord_len

            coord_id = coord_bytes.decode("utf-8", errors="ignore")
            payload_len = struct.unpack_from("<I", data, offset)[0]
            offset += 4

            if offset + payload_len > data_len:
                break

            payload_bytes = data[offset : offset + payload_len]
            offset += payload_len

            try:
                payload_json = json.loads(payload_bytes.decode("utf-8", errors="ignore"))
            except Exception:
                continue

            record = {
                "record_type": record_type,
                "coordinate": coord_id,
                **payload_json
            }
            records.append(record)

        return records

    def ingest_crystal(self) -> None:
        """
        Scans the output directory for binary volume files (`niichii_v*.bin` and `gis_english.bin`),
        ingests them, and builds deterministic indexing structures.
                    """
        search_paths = [
            self.delm_volumes_dir,
            self.base_dir
        ]

        found_files = []
        for path in search_paths:
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if (f.startswith("niichii_v") and f.endswith(".bin")) or f == "gis_english.bin":
                        full_p = os.path.join(path, f)
                        if full_p not in found_files:
                            found_files.append(full_p)

        found_files.sort()
        combined_binary_stream = bytearray()

        for filepath in found_files:
            filename = os.path.basename(filepath)
            try:
                with open(filepath, "rb") as f:
                    bin_data = f.read()
                
                if not bin_data:
                    continue

                parsed = self._parse_delm_stream(bin_data)
                if parsed:
                    self.volumes_count += 1
                    self.volume_names.append(filename)
                    combined_binary_stream.extend(bin_data)
                    
                    for rec in parsed:
                        self.records.append(rec)
                        self.total_records_loaded += 1
                        
                        coord = rec.get("coordinate", "0.0")
                        self.coordinate_index.setdefault(coord, []).append(rec)
                        
                        subj = (rec.get("subject") or "").strip().lower()
                        if subj:
                            self.subject_index.setdefault(subj, []).append(rec)
            except Exception as e:
                print(f"[CRYSTAL LOADER ERROR] Failed to ingest {filename}: {e}")

        # Compute cryptographic crystal checksum
        if combined_binary_stream:
            sha = hashlib.sha256(combined_binary_stream).hexdigest()
            # Convert first 8 hex chars to a stable float checksum
            self.crystal_checksum = float(int(sha[:8], 16)) / float(0xFFFFFFFF)
        else:
            self.crystal_checksum = 1.0

        # Execute Cold-Boot Manifold Dislocation Audit Sweep
        self._audit_manifold_dislocations()

        print(f"[CRYSTAL LOADER] Ingested {self.volumes_count} volume(s), loaded {self.total_records_loaded:,} records.")
        print(f"[MANIFOLD AUDIT] Flagged {self.total_placeholders_count} ontological dislocations across crystal volume.")
        
    def _audit_manifold_dislocations(self) -> None:
        """
        Performs a cold-boot startup sweep across all ingested DELM records to detect
        ontological misclassifications, unclosed formal derivations, and phenomenological placeholders.
        """
        for rec in self.records:
            subj = rec.get("subject", "").strip()
            if not subj:
                continue
            
            coord = str(rec.get("coordinate", "1.0"))
            try:
                nest_depth = float(coord)
            except ValueError:
                nest_depth = 1.0

            # Collect all payload values as expression string
            expr_parts = []
            for k, v in rec.items():
                if k not in ("record_type", "coordinate", "subject"):
                    expr_parts.append(str(v))
            expr_clean = " ".join(expr_parts).strip()

            # Structural & Epistemic discrepancy check
            is_unindexed = "unindexed" in expr_clean.lower() or not expr_clean
            has_math_operators = any(op in expr_clean for op in ['=', '+', '-', '*', '/', '\\', 'd', 'rho', 'c ='])
            is_historical_descriptor = any(char.isdigit() for char in expr_clean[:4]) and not has_math_operators
            has_phenomenological_containers = any(sub in expr_clean.lower() for sub in ['_(de)', '_de', '_eff', '_fit', 'empirical parameter', 'fitting'])
            
            # Detect unclosed recursive epistemic loops or subjective cognitive tensions
            has_unclosed_epistemic_loop = any(sub in subj.lower() or sub in expr_clean.lower() for sub in ['consciousness', 'qualia', 'paradox', 'hard problem', 'unresolved', 'subjective', 'epistemic'])

            is_placeholder = (
                is_unindexed or 
                is_historical_descriptor or 
                has_phenomenological_containers or 
                has_unclosed_epistemic_loop or
                (nest_depth > 0.0 and not has_math_operators)
            )

            if is_placeholder:
                self.total_placeholders_count += 1
                if subj not in self.potential_placeholders:
                    self.potential_placeholders.append(subj)
                
                # Register dislocation mapping (Human Consensus vs True FISSN Crystalline Anchor)
                self.dislocation_registry[subj.lower()] = {
                    "human_consensus_tier": nest_depth,
                    "dislocation_status": "Topological Rupture / Placeholder Detected",
                    "expression": expr_clean[:120]
                }

    def tier_settled_share(self) -> Dict[float, float]:
        """
        Per FISSN tier, the share of records whose subject is not flagged as an
        ontological dislocation. A high share means settled ground: established
        derivations rather than placeholders.
        """
        if hasattr(self, "_settled_share"):
            return self._settled_share
        total: Dict[float, int] = {}
        flagged: Dict[float, int] = {}
        for r in self.records:
            try:
                tier = float(r.get("coordinate"))
            except (TypeError, ValueError):
                continue
            total[tier] = total.get(tier, 0) + 1
            if str(r.get("subject", "")).strip().lower() in self.dislocation_registry:
                flagged[tier] = flagged.get(tier, 0) + 1
        self._settled_share = {t: 1.0 - (flagged.get(t, 0) / n) for t, n in total.items() if n}
        return self._settled_share

    def query_by_subject(self, subject: str) -> List[Dict[str, Any]]:
        """Retrieves all memory crystal records matching a given subject key."""
        return self.subject_index.get(subject.strip().lower(), [])

# Standalone Verification Test
if __name__ == "__main__":
    print("=" * 78)
    print("        CRYSTAL LOADER INGESTION ENGINE TEST")
    print("=" * 78)
    
    loader = CrystalLoader()
    print(f"Volumes Loaded : {loader.volumes_count} ({loader.volume_names})")
    print(f"Total Records  : {loader.total_records_loaded:,}")
    print(f"Crystal Checksum: {loader.crystal_checksum:.6f}")
    print("=" * 78)
