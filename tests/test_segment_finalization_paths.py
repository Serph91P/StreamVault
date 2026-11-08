"""Final output identity is settled before admission, never by renaming a live input."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models import Recording
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_lifecycle_manager import RecordingLifecycleManager
from test_recording_completion_notifications import completion_state as _completion_state, CompletedChild, make_manager

completion_state=_completion_state


@pytest.mark.asyncio
@pytest.mark.parametrize('already_parent',[True,False])
async def test_move_preserves_same_file_and_real_other_target(tmp_path,already_parent):
    segments=tmp_path/'capture_segments'; segments.mkdir()
    final=tmp_path/'capture.ts'; final.write_bytes(b'existing media')
    source=final if already_parent else segments/'capture.ts'
    if not already_parent: source.write_bytes(b'our complete capture')
    info={'segment_dir':str(segments),'base_output_path':str(source)}
    await ProcessManager.__new__(ProcessManager)._move_concatenated_file_to_parent(info)
    if already_parent:
        assert info['final_output_path']==str(final)
        assert final.read_bytes()==b'existing media'
        assert not (tmp_path/'capture_copy1.ts').exists()
    else:
        assert final.read_bytes()==b'existing media'
        assert Path(info['final_output_path']).read_bytes()==b'our complete capture'
        assert info['final_output_path']==str(tmp_path/'capture_copy1.ts')


@pytest.mark.asyncio
async def test_lifecycle_cannot_publish_while_segment_owner_is_finalizing():
    manager=RecordingLifecycleManager.__new__(RecordingLifecycleManager)
    manager.database_service=SimpleNamespace(get_recording_by_id=lambda _:Recording(stream_id=7))
    manager.process_manager=SimpleNamespace(active_processes={},long_stream_processes={'stream_7':{}})
    assert await manager._check_recording_process(1) is True
    manager.process_manager.long_stream_processes.clear()
    assert await manager._check_recording_process(1) is False


@pytest.mark.asyncio
async def test_concat_preserves_other_final_before_admitting_one_stable_path(completion_state,monkeypatch):
    state=completion_state; child=CompletedChild(); manager=make_manager(state,child)
    directory=state.root/'capture_segments'; directory.mkdir()
    segment=directory/'capture_part001.ts'; segment.write_bytes(b'our captured bytes')
    final=state.root/'capture.ts'; final.write_bytes(b'foreign complete media')
    info={'segment_dir':str(directory),'base_output_path':str(final),'stream_id':state.stream_id,'recording_id':963,'monitor_task':None,'total_segments':[{'path':str(segment)}]}
    async def concatenate(*command,**_):
        Path(command[-1]).write_bytes(segment.read_bytes())
        return CompletedChild()
    monkeypatch.setattr(asyncio,'create_subprocess_exec',concatenate)
    admissions=[]
    async def admitted(recording_id,path):
        assert final.read_bytes()==b'foreign complete media'
        assert Path(path).read_bytes()==b'our captured bytes'
        admissions.append((recording_id,path))
    manager.post_processing_callback=admitted
    await manager._finalize_segmented_recording(info)
    assert admissions==[(963,str(state.root/'capture_copy1.ts'))]
    assert final.read_bytes()==b'foreign complete media'
    assert Path(admissions[0][1]).read_bytes()==b'our captured bytes'
