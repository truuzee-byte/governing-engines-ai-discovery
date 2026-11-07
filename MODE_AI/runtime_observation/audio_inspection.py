"""Bounded PCM measurements; waveform inspection is not playback or quality validation."""
import hashlib
import io
import wave

MAX_BYTES=8*1024*1024


def inspect_pcm(content,expected_hash):
    if type(content) is not bytes or len(content)>MAX_BYTES:raise ValueError('Bounded WAV bytes required')
    actual=hashlib.sha256(content).hexdigest()
    if actual!=expected_hash:raise ValueError('Audio source hash mismatch')
    result={'schema_version':'PCMInspection/1','source_sha256':actual,'state':'UNINSPECTABLE',
            'metrics':None,'playback_observed':False,'quality_validated':False}
    try:
        with wave.open(io.BytesIO(content),'rb') as reader:
            channels=reader.getnchannels();width=reader.getsampwidth();rate=reader.getframerate();frames=reader.getnframes()
            if reader.getcomptype()!='NONE' or width not in {1,2,3,4} or not 1<=channels<=32 or rate<=0:
                raise ValueError('Unsupported PCM representation')
            if frames*channels*width>MAX_BYTES:raise ValueError('Declared PCM exceeds inspection bound')
            raw=reader.readframes(frames)
            partial=len(raw)!=frames*channels*width
            observed_frames=len(raw)//(channels*width)
            remainder=len(raw)%(channels*width)
            raw=raw[:observed_frames*channels*width]
            if partial:result.update(reason='TRUNCATED_PCM')
            peaks=[0]*channels;nonzero=[0]*channels
            for offset in range(0,len(raw),width):
                sample=(raw[offset]-128) if width==1 else int.from_bytes(raw[offset:offset+width],'little',signed=True)
                channel=(offset//width)%channels
                peaks[channel]=max(peaks[channel],abs(sample));nonzero[channel]+=int(sample!=0)
            result.update(state='PARTIAL' if partial else 'MEASURED',metrics={'channels':channels,'sample_width_bytes':width,'sample_rate_hz':rate,
                'sample_frames':observed_frames,'declared_sample_frames':frames,'missing_sample_frames':frames-observed_frames,
                'uninterpreted_partial_frame_bytes':remainder,'measurement_scope':'OBSERVED_COMPLETE_PCM_FRAMES',
                'duration_seconds':observed_frames/rate,'peak_absolute_integer':peaks if observed_frames else [None]*channels,
                'nonzero_samples':nonzero,'nonzero_fraction':[v/observed_frames if observed_frames else None for v in nonzero]})
    except (wave.Error,EOFError,ValueError) as exc:
        result['error_type']=type(exc).__name__
    return result
