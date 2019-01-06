import json
import pylab as pl
import random
import numpy as np
#import cv2
import copy

type42 = "i2,i4,i5,il100,il60,il80,ip,p10,p11,p12,p19,p23,p26,p27,p3,p5,p6,pg,ph4,ph4.5,ph5,pl100,pl120,pl20,pl30,pl40,pl5,pl50,pl60,pl70,pl80,pm20,pm30,pm55,pn,pne,pr40,w13,w32,w55,w57,w59"
type42 = type42.split(',')

type3 = "z,j,s"
type3 = type3.split(',')

type5 = "z,j,s,l,d"
type5 = type5.split(',')


def rect_cross(rect1, rect2):
    rect = [max(rect1[0], rect2[0]),
            max(rect1[1], rect2[1]),
            min(rect1[2], rect2[2]),
            min(rect1[3], rect2[3])]
    rect[2] = max(rect[2], rect[0])
    rect[3] = max(rect[3], rect[1])
    return rect

def rect_area(rect):
    return float(max(0.0, (rect[2]-rect[0])*(rect[3]-rect[1])))

def calc_cover(rect1, rect2):
    crect = rect_cross(rect1, rect2)
    return rect_area(crect) / rect_area(rect2)

def calc_iou(rect1, rect2):
    crect = rect_cross(rect1, rect2)
    ac = rect_area(crect)
    a1 = rect_area(rect1)
    a2 = rect_area(rect2)
    return ac / (a1+a2-ac)

def get_refine_rects(annos, raw_rects, minscore=20):
    cover_th = 0.5
    refine_rects = {}

    for imgid in raw_rects.keys():
        v = raw_rects[imgid]
        tv = copy.deepcopy(sorted(v, key=lambda x:-x[2]))
        nv = []
        for obj in tv:
            rect = obj[1]
            rect[2]+=rect[0]
            rect[3]+=rect[1]
            if rect_area(rect) == 0: continue
            if obj[2] < minscore: continue
            cover_area = 0
            for obj2 in nv:
                cover_area += calc_cover(obj2[1], rect)
            if cover_area < cover_th:
                nv.append(obj)
        refine_rects[imgid] = nv
    results = {}
    for imgid, v in refine_rects.items():
        objs = []
        for obj in v:
            mobj = {"bbox":dict(zip(["xmin","ymin","xmax","ymax"], obj[1])), 
                    "category":annos['types'][int(obj[0]-1)], "score":obj[2]}
            objs.append(mobj)
        results[imgid] = {"objects":objs}
    results_annos = {"imgs":results}
    return results_annos

def box_long_size(box):
    return max(box['xmax']-box['xmin'], box['ymax']-box['ymin'])

def eval_annos(annos_gd, annos_rt, iou=0.5, imgids=None, check_type=True, types=None, minscore=40, minboxsize=0, maxboxsize=512, match_same=True):
    ac_n, ac_c = 0,0
    rc_n, rc_c = 0,0
    if imgids==None:
        imgids = annos_rt['imgs'].keys()
    if types!=None:
        types = { t:0 for t in types }
    miss = {"imgs":{}}
    wrong = {"imgs":{}}
    right = {"imgs":{}}
    
    for imgid in imgids:
        v = annos_rt['imgs'][imgid]
        vg = annos_gd['imgs'][imgid]
        convert = lambda objs: [ [ obj['bbox'][key] for key in ['xmin','ymin','xmax','ymax']] for obj in objs]
        objs_g = vg["objects"]
        objs_r = v["objects"]
        bg = convert(objs_g)
        br = convert(objs_r)
        
        match_g = [-1]*len(bg)
        match_r = [-1]*len(br)
        if types!=None:
            for i in range(len(match_g)):
                if not types.has_key(objs_g[i]['category']):
                    match_g[i] = -2
            for i in range(len(match_r)):
                if not types.has_key(objs_r[i]['category']):
                    match_r[i] = -2
        for i in range(len(match_r)):
            if objs_r[i].has_key('score') and objs_r[i]['score']<minscore:
                match_r[i] = -2
        matches = []
        for i,boxg in enumerate(bg):
            for j,boxr in enumerate(br):
                if match_g[i] == -2 or match_r[j] == -2:
                    continue
                #if match_same and objs_g[i]['category'] != objs_r[j]['category']: continue
                tiou = calc_iou(boxg, boxr)
                if tiou>iou:
                    matches.append((tiou, i, j))
        matches = sorted(matches, key=lambda x:-x[0])
        for tiou, i, j in matches:
            if match_g[i] == -1 and match_r[j] == -1:
                match_g[i] = j
                match_r[j] = i
                
        for i in range(len(match_g)):
            boxsize = box_long_size(objs_g[i]['bbox'])
            erase = False
            if not (boxsize>=minboxsize and boxsize<maxboxsize):
                erase = True
            #if types!=None and not types.has_key(objs_g[i]['category']):
            #    erase = True
            if erase:
                if match_g[i] >= 0:
                    match_r[match_g[i]] = -2
                match_g[i] = -2
        
        for i in range(len(match_r)):
            boxsize = box_long_size(objs_r[i]['bbox'])
            if match_r[i] != -1: continue
            if not (boxsize>=minboxsize and boxsize<maxboxsize):
                match_r[i] = -2
                    
        miss["imgs"][imgid] = {"objects":[]}
        wrong["imgs"][imgid] = {"objects":[]}
        right["imgs"][imgid] = {"objects":[]}
        miss_objs = miss["imgs"][imgid]["objects"]
        wrong_objs = wrong["imgs"][imgid]["objects"]
        right_objs = right["imgs"][imgid]["objects"]
        
        tt = 0
        for i in range(len(match_g)):
            if match_g[i] == -1:
                miss_objs.append(objs_g[i])
        for i in range(len(match_r)):
            if match_r[i] == -1:
                obj = copy.deepcopy(objs_r[i])
                obj['correct_catelog'] = 'none'
                wrong_objs.append(obj)
            elif match_r[i] != -2:
                j = match_r[i]
                obj = copy.deepcopy(objs_r[i])
                if not check_type or objs_g[j]['category'] == objs_r[i]['category']:
                    right_objs.append(objs_r[i])
                    tt+=1
                else:
                    obj['correct_catelog'] = objs_g[j]['category']
                    wrong_objs.append(obj)
                    
        
        rc_n += len(objs_g) - match_g.count(-2)
        ac_n += len(objs_r) - match_r.count(-2)
        
        ac_c += tt
        rc_c += tt
    if types==None:
        styps = "all"
    elif len(types)==1:
        styps = types.keys()[0]
    elif not check_type or len(types)==0:
        styps = "none"
    else:
        styps = "[%s, ...total %s...]"%(types.keys()[0], len(types))
    report = "iou:%s, size:[%s,%s), types:%s, accuracy:%s, recall:%s"% (
        iou, minboxsize, maxboxsize, styps, 1 if ac_n==0 else ac_c*1.0/ac_n, 1 if rc_n==0 else rc_c*1.0/rc_n)
    summury = {
        "iou":iou,
        "accuracy":1 if ac_n==0 else ac_c*1.0/ac_n,
        "recall":1 if rc_n==0 else rc_c*1.0/rc_n,
        "miss":miss,
        "wrong":wrong,
        "right":right,
        "report":report
    }
    return summury
