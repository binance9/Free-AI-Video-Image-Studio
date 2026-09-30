class ReferenceResolver:
    def resolve(self,intent,context):
        refs=list(getattr(intent,'context_references',[]) or []); resolved={}; unresolved=[]
        m=context.get('references_map') or {}
        for ref in refs:
            key=str(ref).strip().lower(); val=m.get(key)
            if val is not None: resolved[ref]=val; continue
            if key in {'nó','no','cái đó','cai do','bản vừa rồi','ban vua roi'}:
                val=context.get('current_files') or context.get('current_artifact') or context.get('current_target')
            elif key in {'mấy lỗi đó','may loi do'}: val=context.get('last_identified_problems')
            elif 'ảnh' in key or 'anh' in key or 'hình' in key or 'hinh' in key or key in {'current_image','image','attachment'}: val=context.get('current_image')
            elif key in {'current_target','target'}: val=context.get('current_target')
            elif key in {'current_files','files'}: val=context.get('current_files')
            elif key in {'current_artifact','artifact'}: val=context.get('current_artifact')
            else: val=None
            if val: resolved[ref]=val
            else: unresolved.append(ref)
        return {'resolved':resolved,'unresolved':unresolved,'confidence':1.0 if refs and not unresolved else (0.0 if unresolved else 1.0)}
