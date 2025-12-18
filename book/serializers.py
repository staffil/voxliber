from rest_framework import serializers
from book.models import Books, Genres, Content
from register.models import Users
from main.models import Advertisment


class GenreSerializer(serializers.ModelSerializer):
    """장르 시리얼라이저"""
    class Meta:
        model = Genres
        fields = ['id', 'name', 'description']


class AuthorSerializer(serializers.ModelSerializer):
    """작가 시리얼라이저"""
    class Meta:
        model = Users
        fields = ['id', 'nickname', 'email']


class BookSerializer(serializers.ModelSerializer):
    """책 시리얼라이저 (홈 페이지용 - 에피소드 수 포함)"""
    author = AuthorSerializer(source='user', read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    cover_img = serializers.SerializerMethodField()
    episode_count = serializers.SerializerMethodField()

    class Meta:
        model = Books
        fields = [
            'id', 'name', 'description', 'cover_img', 'book_score',
            'created_at', 'author', 'genres', 'episode_count'
        ]

    def get_cover_img(self, obj):
        """커버 이미지 절대 URL 반환"""
        if obj.cover_img:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.cover_img.url)
        return None

    def get_episode_count(self, obj):
        """에피소드(콘텐츠) 수 반환"""
        return obj.contents.count()


class BannerSerializer(serializers.ModelSerializer):
    """배너(광고) 시리얼라이저"""
    advertisment_img = serializers.SerializerMethodField()

    class Meta:
        model = Advertisment
        fields = ['id', 'link', 'advertisment_img']

    def get_advertisment_img(self, obj):
        """배너 이미지 절대 URL 반환"""
        if obj.advertisment_img:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.advertisment_img.url)
        return None
