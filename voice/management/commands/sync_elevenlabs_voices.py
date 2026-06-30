import os
import requests
from django.core.management.base import BaseCommand
from book.models import VoiceList


class Command(BaseCommand):
    help = 'ElevenLabs API에서 voice preview_url 동기화'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='DB 저장 없이 결과만 출력',
        )

    def handle(self, *args, **options):
        api_key = os.getenv('ELEVENLABS_API_KEY')
        if not api_key:
            self.stderr.write(self.style.ERROR('ELEVENLABS_API_KEY 환경변수가 없습니다.'))
            return

        self.stdout.write('ElevenLabs API 호출 중...')

        try:
            resp = requests.get(
                'https://api.elevenlabs.io/v1/voices',
                headers={'xi-api-key': api_key},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f'API 호출 실패: {e}'))
            return

        voices = resp.json().get('voices', [])
        self.stdout.write(f'ElevenLabs에서 {len(voices)}개 보이스 수신')

        updated = 0
        skipped = 0

        for v in voices:
            voice_id = v.get('voice_id')
            preview_url = v.get('preview_url')

            if not voice_id or not preview_url:
                continue

            try:
                voice = VoiceList.objects.get(voice_id=voice_id)
            except VoiceList.DoesNotExist:
                skipped += 1
                continue

            if options['dry_run']:
                self.stdout.write(f'  [DRY] {voice.voice_name} → {preview_url}')
            else:
                voice.preview_url = preview_url
                voice.save(update_fields=['preview_url'])
                self.stdout.write(f'  업데이트: {voice.voice_name}')
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'완료 — 업데이트 {updated}개 / DB 없음(스킵) {skipped}개'
        ))
