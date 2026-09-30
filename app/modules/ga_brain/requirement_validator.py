from pathlib import Path
class RequirementValidator:
    PHYSICAL_KEYS={'backup_confirmed','file_exists','target_exists','write_confirmed','syntax_pass','test_pass','tests_pass','artifact_exists','output_exists'}
    def validate(self,tool,plan,context):
        # Never accept model/planner assertions as proof of physical state.
        for k in self.PHYSICAL_KEYS:
            if k in (plan.fields or {}): return False,'untrusted_physical_assertion'
        for req in tool.requirements:
            r=req.lower()
            if 'resolved target' in r and not plan.target:return False,'missing_target'
            if 'resolved path' in r:
                p=(plan.fields or {}).get('path') or (plan.files[0] if plan.files else None)
                if not p:return False,'missing_target'
            if 'existing file' in r or 'file exists' in r:
                p=(plan.fields or {}).get('path') or (plan.files[0] if plan.files else None)
                if not p or not Path(p).exists():return False,'file_not_found'
            if 'image loaded' in r and not context.get('current_image') and not context.get('attachment'):return False,'missing_required_input'
            if 'backup' in r and tool.side_effects:
                # Backup is an executor responsibility. Preflight requires a resolved existing target, not a model boolean.
                p=(plan.fields or {}).get('path') or (plan.files[0] if plan.files else None)
                if not p:return False,'missing_target'
                if not Path(p).exists():return False,'file_not_found'
            if 'required arguments' in r and not plan.fields and not plan.files:return False,'missing_required_input'
        return True,'requirements_ok'
