from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


def _dedupe_existing(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        lowered = resolved.lower()
        if lowered in seen:
            continue
        if path.exists():
            seen.add(lowered)
            result.append(path)
    return result


def _path_entries() -> list[Path]:
    raw = os.environ.get('PATH', '')
    return [Path(item) for item in raw.split(os.pathsep) if item]


def _possible_roots() -> list[Path]:
    home = Path.home()
    roots: list[Path] = []

    for env_name in ('OSGEO4W_ROOT', 'GDAL_HOME', 'GEOS_LIBRARY_PATH', 'GDAL_LIBRARY_PATH'):
        value = os.environ.get(env_name)
        if not value:
            continue
        candidate = Path(value)
        roots.append(candidate.parent if candidate.suffix else candidate)

    roots.extend(
        [
            Path(r'C:\OSGeo4W'),
            Path(r'C:\OSGeo4W64'),
            Path(r'C:\Program Files\OSGeo4W'),
            Path(r'C:\Program Files\QGIS'),
            Path(r'C:\Program Files\GDAL'),
            Path(r'C:\Program Files\PostgreSQL'),
            Path(sys.prefix),
            Path(sys.base_prefix),
            home / 'AppData' / 'Local' / 'Programs' / 'Python',
            home / 'AppData' / 'Local' / 'Programs' / 'QGIS',
        ]
    )
    roots.extend(_path_entries())
    return _dedupe_existing(roots)


def _search_dirs() -> list[Path]:
    dirs: list[Path] = []
    for root in _possible_roots():
        candidates = [
            root,
            root / 'bin',
            root / 'Library' / 'bin',
            root / 'Lib' / 'site-packages' / 'osgeo',
            root / 'lib' / 'site-packages' / 'osgeo',
            root / 'apps' / 'Python313' / 'Lib' / 'site-packages' / 'osgeo',
            root / 'apps' / 'Python312' / 'Lib' / 'site-packages' / 'osgeo',
            root / 'apps' / 'Python311' / 'Lib' / 'site-packages' / 'osgeo',
            root / 'apps' / 'Python310' / 'Lib' / 'site-packages' / 'osgeo',
        ]

        if root.name.lower() == 'python':
            candidates.extend(root.glob('Python*'))
        if root.name.lower() == 'postgresql':
            candidates.extend(root.glob('*/bin'))
        if root.name.lower() == 'qgis':
            candidates.extend(root.glob('**/bin'))
            candidates.extend(root.glob('**/apps/Python*/Lib/site-packages/osgeo'))
        if root.name.lower().startswith('osgeo4w'):
            candidates.extend(root.glob('apps/Python*/Lib/site-packages/osgeo'))

        dirs.extend(candidates)

    return _dedupe_existing(dirs)


def _pick_best(patterns: list[str]) -> Path | None:
    matches: list[Path] = []
    for directory in _search_dirs():
        for pattern in patterns:
            matches.extend(directory.glob(pattern))
    files = [match for match in matches if match.is_file()]
    if not files:
        return None

    def sort_key(path: Path):
        stem = path.stem.lower()
        digits = ''.join(ch for ch in stem if ch.isdigit())
        return (len(digits), digits, stem)

    return sorted(files, key=sort_key, reverse=True)[0]


def _set_if_missing(name: str, value: Path | str | None) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    if value:
        os.environ[name] = str(value)
        return os.environ[name]
    return None


def _prepend_path(directory: Path | None) -> None:
    if not directory or not directory.exists():
        return
    current = os.environ.get('PATH', '')
    prefix = str(directory)
    entries = current.split(os.pathsep) if current else []
    lowered = {entry.lower() for entry in entries}
    if prefix.lower() not in lowered:
        os.environ['PATH'] = prefix + os.pathsep + current if current else prefix


def configure_geospatial_environment() -> dict[str, str | None]:
    if os.name != 'nt':
        return {
            'GDAL_LIBRARY_PATH': os.environ.get('GDAL_LIBRARY_PATH'),
            'GEOS_LIBRARY_PATH': os.environ.get('GEOS_LIBRARY_PATH'),
            'GDAL_DATA': os.environ.get('GDAL_DATA'),
            'PROJ_LIB': os.environ.get('PROJ_LIB'),
        }

    gdal_path = _pick_best(['gdal*.dll', 'libgdal*.dll'])
    geos_path = _pick_best(['geos_c*.dll', 'libgeos_c*.dll'])

    gdal_value = _set_if_missing('GDAL_LIBRARY_PATH', gdal_path)
    geos_value = _set_if_missing('GEOS_LIBRARY_PATH', geos_path)

    if gdal_path:
        _prepend_path(gdal_path.parent)

    osgeo_root = os.environ.get('OSGEO4W_ROOT')
    if not osgeo_root and gdal_path:
        candidate_root = gdal_path.parent.parent
        if candidate_root.exists():
            os.environ['OSGEO4W_ROOT'] = str(candidate_root)
            osgeo_root = str(candidate_root)

    data_candidates: list[Path] = []
    proj_candidates: list[Path] = []
    for root in _possible_roots():
        data_candidates.extend(
            [
                root / 'share' / 'gdal',
                root / 'apps' / 'gdal' / 'share' / 'gdal',
                root / 'Library' / 'share' / 'gdal',
            ]
        )
        proj_candidates.extend(
            [
                root / 'share' / 'proj',
                root / 'apps' / 'proj' / 'share' / 'proj',
                root / 'Library' / 'share' / 'proj',
            ]
        )

    gdal_data = next((path for path in _dedupe_existing(data_candidates) if path.exists()), None)
    proj_lib = next((path for path in _dedupe_existing(proj_candidates) if path.exists()), None)

    _set_if_missing('GDAL_DATA', gdal_data)
    _set_if_missing('PROJ_LIB', proj_lib)

    return {
        'GDAL_LIBRARY_PATH': gdal_value,
        'GEOS_LIBRARY_PATH': geos_value,
        'GDAL_DATA': os.environ.get('GDAL_DATA'),
        'PROJ_LIB': os.environ.get('PROJ_LIB'),
        'OSGEO4W_ROOT': osgeo_root,
    }
