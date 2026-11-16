"""Native two-thread/two-session PostgreSQL adoption proof; disposable DB only.

Run with STREAMVAULT_POSTGRES_TEST_URL pointing to an owned empty test database.
No provider, processing, migration or production-data claim is made.
"""

import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Recording, Stream, Streamer
from app.services.recording.unified_recovery_service import UnifiedRecoveryService


def main() -> None:
    url = os.environ["STREAMVAULT_POSTGRES_TEST_URL"]
    engine = create_engine(url)
    if engine.dialect.name != "postgresql":
        raise ValueError("This gate requires real isolated PostgreSQL")
    if inspect(engine).get_table_names():
        raise ValueError("This gate requires an empty owned test database")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        if db.scalar(select(Streamer.id)) is not None:
            raise ValueError("This gate requires an empty owned test database")
        db.add(Streamer(username="synthetic951", twitch_id="synthetic951"))
        db.commit()
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="951-adoption-") as temporary:
            directory = Path(temporary) / "recordings" / "synthetic951" / "Season 2026"
            directory.mkdir(parents=True)
            for kind in ("segments", "ts"):
                path = directory / f"synthetic951_{kind}.ts"
                if kind == "ts":
                    path.write_bytes(b"synthetic original TS")
                else:
                    segments = directory / f"synthetic951_{kind}_segments"
                    segments.mkdir()
                    (segments / "segment_001.ts").write_bytes(
                        b"synthetic original segment"
                    )
                start = Barrier(2)

                def adopt() -> int | None:
                    with factory() as db:
                        start.wait(timeout=10)
                        return UnifiedRecoveryService()._create_recording_from_orphaned_path(
                            db, str(path)
                        )

                with ThreadPoolExecutor(max_workers=2) as workers:
                    jobs = [workers.submit(adopt) for _ in range(2)]
                    ids = [job.result(timeout=15) for job in jobs]
                assert ids[0] is not None and ids[0] == ids[1], ids
                with factory() as db:
                    rows = db.scalars(
                        select(Recording).where(Recording.path == str(path))
                    ).all()
                    assert len(rows) == 1
                    assert db.get(Stream, rows[0].stream_id) is not None
                results.append(
                    {
                        "kind": kind,
                        "actors": 2,
                        "recording_rows": len(rows),
                        "same_identity": True,
                    }
                )
        print(json.dumps({"postgresql": True, "adoptions": results}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
