
from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Home page
    path("", views.home, name="home"),

    # Authentication
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),

    # Quiz History
    path("quiz-history/", views.quiz_history, name="quiz_history"),

    # Categories and Topics
    path("categories/", views.categories, name="categories"),
    path("topic/<int:topic_id>/", views.topic_detail, name="topic_detail"),
    path("random-topic/", views.random_topic, name="random_topic"),

    # Quiz
    path("quiz/<int:topic_id>/", views.quiz, name="quiz"),

    # Leaderboard
    path("leaderboard/", views.leaderboard, name="leaderboard"),
]
