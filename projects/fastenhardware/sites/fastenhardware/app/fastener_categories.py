from .runner_state import ReviewRequired
BRANCHES={'Screws','Bolts','Nuts','Washers','Rivets','Anchors','Threaded Rods & Studs'}
def ensure_path(store, path):
    if not isinstance(path,list) or len(path)<2 or path[0]!='Fasteners' or path[1] not in BRANCHES:
        raise ReviewRequired('FASTENER_CATEGORY_PATH_UNVERIFIED')
    if any(not isinstance(name,str) or not name.strip() for name in path):
        raise ReviewRequired('EMPTY_CATEGORY_NAME')
    parent=0
    for name in path:
        matches=[c for c in store.categories if c['name']==name and c.get('parent',0)==parent]
        if len(matches)>1: raise ReviewRequired('AMBIGUOUS_CATEGORY_PATH')
        if not matches:
            created=store.client.post('products/categories',{'name':name,'parent':parent})
            live=store.client.get('products/categories/'+str(created['id']))
            if live['name']!=name or live['parent']!=parent: raise ReviewRequired('CATEGORY_READBACK_FAIL')
            store.categories.append(live); matches=[live]
        parent=matches[0]['id']
    return path[-1]
