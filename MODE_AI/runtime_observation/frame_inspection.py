"""Bounded pixel measurements, not judgments about motion, meaning, or render success."""
import base64
import hashlib
import io
import json


def inspect_frames(contents):
    from PIL import Image,ImageChops,ImageStat
    if type(contents) is not list or not 1<=len(contents)<=32:raise ValueError('Select between one and 32 frames')
    def unique(pairs):
        data={}
        for key,value in pairs:
            if key in data:raise ValueError('Duplicate image source field')
            data[key]=value
        return data
    def read_frame(content,index,measurement):
        if type(content) is not str or len(content)>12*1024*1024:raise ValueError('Encoded frame bound exceeded')
        value=json.loads(content,object_pairs_hook=unique)
        if type(value) is not dict or set(value)!={'schema_version','encoding','data','sha256'} or value['schema_version']!='ImageSource/1' or value['encoding']!='BASE64':
            raise ValueError('Exact encoded image source required')
        raw=base64.b64decode(value['data'],validate=True)
        if len(raw)>8*1024*1024 or hashlib.sha256(raw).hexdigest()!=value['sha256']:raise ValueError('Frame hash/size mismatch')
        measurement.update(sha256=value['sha256'],source_hash_state='VERIFIED')
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {'PNG','JPEG','WEBP'} or getattr(image,'n_frames',1)!=1:
                raise ValueError('Explicit individual supported frames required')
            if image.width*image.height>4*1024*1024:raise ValueError('Frame pixel bound exceeded')
            with image.convert('RGBA') as rgba:
                with rgba.getchannel('A') as channel:alpha=channel.getextrema()
            frame=image.convert('RGB');stats=ImageStat.Stat(frame)
            measurement.update(state='MEASURED',width=image.width,height=image.height,
                rgb_extrema=[list(v) for v in frame.getextrema()],rgb_mean=stats.mean,alpha_extrema=list(alpha))
        return frame
    measurements=[];previous=None;differences=[];unavailable=[]
    for index,content in enumerate(contents):
        frame=None
        measurement={'index':index,'state':'UNINSPECTABLE','sha256':None,'source_hash_state':'UNAVAILABLE',
            'width':None,'height':None,'rgb_extrema':None,'rgb_mean':None,'alpha_extrema':None}
        try:
            frame=read_frame(content,index,measurement)
        except (ValueError,TypeError,KeyError,OSError,Image.DecompressionBombError) as exc:
            measurement['error_type']=type(exc).__name__
            unavailable.append({'frame_index':index,'reason':'UNINSPECTABLE'})
        measurements.append(measurement)
        if index:
            if previous is None or frame is None:
                differences.append({'from_index':index-1,'to_index':index,'state':'UNAVAILABLE_FRAME','rgb_mean_absolute_difference':None})
            elif previous.size!=frame.size:
                differences.append({'from_index':index-1,'to_index':index,'state':'UNAVAILABLE_DIMENSION_MISMATCH','rgb_mean_absolute_difference':None})
            else:
                with ImageChops.difference(previous,frame) as difference:
                    differences.append({'from_index':index-1,'to_index':index,'state':'MEASURED','rgb_mean_absolute_difference':ImageStat.Stat(difference).mean})
        if previous is not None:previous.close()
        previous=frame
    if previous is not None:previous.close()
    unavailable.extend({'from_index':d['from_index'],'to_index':d['to_index'],'reason':d['state']}
        for d in differences if d['state']!='MEASURED')
    return {'contract':'FrameSourceInspection/1','state':'PARTIAL' if unavailable else 'MEASURED',
        'unavailable_measurements':unavailable,'frames':measurements,'differences':differences,
        'temporal_order':'OPERATOR_SELECTED_ORDER','render_execution_observed':False,'motion_validated':False,
        'creative_quality_validated':False,'playback_observed':False}
