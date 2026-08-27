from __future__ import annotations
import argparse
import json
from pathlib import Path
import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True)
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--url', default='http://127.0.0.1:8012')
    ap.add_argument('--strength', type=float, default=0.28)
    args = ap.parse_args()
    image = Path(args.image).expanduser().resolve()
    if not image.is_file():
        raise SystemExit(f'Image not found: {image}')
    with image.open('rb') as fh:
        files = {'image': (image.name, fh, 'application/octet-stream')}
        data = {
            'prompt': args.prompt,
            'size': '1024x1024',
            'style': 'fantasy',
            'quality': 'medium',
            'min_score': '70',
            'max_repairs': '3',
            'strength': str(args.strength),
            'preset': 'compact_game',
        }
        r = requests.post(args.url + '/character-2d/from-reference', files=files, data=data, timeout=900)
    print('HTTP', r.status_code)
    try:
        payload = r.json()
    except Exception:
        print(r.text)
        raise SystemExit(1)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if r.ok and payload.get('accepted') and payload.get('image'):
        print('\n[OK] Generated:', payload['image'])
    else:
        print('\n[REJECTED] Check blockers/export_gate above.')

if __name__ == '__main__':
    main()
