
import random
import re
import unicodedata
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone

from .models import Category, Topic, QuizQuestion, QuizAttempt


def normalize_answer(value):
    """Normalize answer text before comparing quiz answers."""
    if value is None:
        return ""

    value = unicodedata.normalize("NFKC", str(value))
    value = value.strip().casefold()
    value = re.sub(r"\s+", " ", value)

    return value


def calculate_streak(user):
    """Return the user's current and longest daily quiz streak."""
    completed_dates = QuizAttempt.objects.filter(
        user=user
    ).values_list("completed_at", flat=True)

    quiz_dates = set()

    for completed_at in completed_dates:
        if completed_at is not None:
            if timezone.is_aware(completed_at):
                quiz_date = timezone.localtime(completed_at).date()
            else:
                quiz_date = completed_at.date()

            quiz_dates.add(quiz_date)

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    if today in quiz_dates:
        check_date = today
    elif yesterday in quiz_dates:
        check_date = yesterday
    else:
        check_date = None

    current_streak = 0

    while check_date is not None and check_date in quiz_dates:
        current_streak += 1
        check_date -= timedelta(days=1)

    best_streak = 0
    running_streak = 0
    previous_date = None

    for quiz_date in sorted(quiz_dates):
        if (
            previous_date is not None
            and (quiz_date - previous_date).days == 1
        ):
            running_streak += 1
        else:
            running_streak = 1

        best_streak = max(best_streak, running_streak)
        previous_date = quiz_date

    return current_streak, best_streak


def home(request):
    categories = Category.objects.all()
    return render(
        request,
        "home.html",
        {"categories": categories},
    )


def signup(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get(
            "confirm_password",
            password,
        )

        if not username or not password:
            messages.error(request, "Please fill in all required fields.")
            return redirect("signup")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("signup")

        if email and User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("signup")

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        messages.success(
            request,
            "Account created successfully. Please log in.",
        )
        return redirect("login")

    return render(request, "signup.html")


def login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            auth_login(request, user)
            return redirect("dashboard")

        messages.error(
            request,
            "Invalid username or password.",
        )

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("home")


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")

    attempts = QuizAttempt.objects.filter(user=request.user)

    topics_learned = attempts.values("topic_id").distinct().count()
    quizzes_completed = attempts.count()

    total_score = (
        attempts.aggregate(total=Sum("score"))["total"] or 0
    )

    total_questions = (
        attempts.aggregate(total=Sum("total_questions"))[
            "total"
        ] or 0
    )

    if total_questions > 0:
        accuracy = round(
            (total_score / total_questions) * 100
        )
    else:
        accuracy = 0

    best_score = 0

    for attempt in attempts:
        if attempt.total_questions:
            attempt_percentage = round(
                (attempt.score / attempt.total_questions) * 100
            )
            best_score = max(best_score, attempt_percentage)

    current_streak, best_streak = calculate_streak(request.user)

    context = {
        "topics_learned": topics_learned,
        "quizzes_completed": quizzes_completed,
        "total_score": total_score,
        "total_questions": total_questions,
        "accuracy": accuracy,
        "best_score": best_score,
        "current_streak": current_streak,
        "best_streak": best_streak,
    }

    return render(request, "dashboard.html", context)


def quiz_history(request):
    if not request.user.is_authenticated:
        return redirect("login")

    attempts = QuizAttempt.objects.filter(
        user=request.user
    ).select_related("topic").order_by("-completed_at")

    return render(
        request,
        "quiz_history.html",
        {"attempts": attempts},
    )


def categories(request):
    all_categories = Category.objects.all()
    selected_category = request.GET.get(
        "category",
        "",
    ).strip()

    topics = Topic.objects.select_related("category").all()

    if selected_category:
        if selected_category.isdigit():
            topics = topics.filter(
                category_id=int(selected_category)
            )
        else:
            topics = topics.filter(
                category__slug=selected_category
            )

    return render(
        request,
        "categories.html",
        {
            "categories": all_categories,
            "topics": topics,
            "selected_category": selected_category,
        },
    )


def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)

    return render(
        request,
        "topic_detail.html",
        {"topic": topic},
    )


def random_topic(request):
    topics = list(Topic.objects.all())

    if not topics:
        messages.info(request, "No topics are available yet.")
        return redirect("categories")

    topic = random.choice(topics)
    return redirect("topic_detail", topic_id=topic.id)


def quiz(request, topic_id):
    if not request.user.is_authenticated:
        return redirect("login")

    topic = get_object_or_404(Topic, id=topic_id)
    questions = list(
        QuizQuestion.objects.filter(topic=topic)
    )

    if not questions:
        messages.info(
            request,
            "No quiz questions are available for this topic yet.",
        )
        return redirect("topic_detail", topic_id=topic.id)

    if request.method == "POST":
        score = 0
        results = []

        for question in questions:
            selected_answer = request.POST.get(
                f"question_{question.id}",
                "",
            )

            correct_answer = question.correct_answer

            is_correct = (
                normalize_answer(selected_answer)
                == normalize_answer(correct_answer)
            )

            if is_correct:
                score += 1

            results.append({
                "question": question,
                "selected_answer": selected_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            })

        total = len(questions)
        percentage = round((score / total) * 100) if total else 0

        QuizAttempt.objects.create(
            user=request.user,
            topic=topic,
            score=score,
            total_questions=total,
        )

        return render(
            request,
            "result.html",
            {
                "topic": topic,
                "score": score,
                "total": total,
                "percentage": percentage,
                "results": results,
            },
        )

    return render(
        request,
        "quiz.html",
        {
            "topic": topic,
            "questions": questions,
        },
    )


def leaderboard(request):
    users = User.objects.filter(
        quizattempt__isnull=False
    ).distinct()

    leaderboard_data = []

    for user in users:
        attempts = QuizAttempt.objects.filter(user=user)

        total_score = (
            attempts.aggregate(total=Sum("score"))["total"] or 0
        )

        total_questions = (
            attempts.aggregate(total=Sum("total_questions"))[
                "total"
            ] or 0
        )

        percentage = (
            round((total_score / total_questions) * 100)
            if total_questions
            else 0
        )

        leaderboard_data.append({
            "user": user,
            "total_score": total_score,
            "total_questions": total_questions,
            "accuracy": percentage,
            "quizzes_completed": attempts.count(),
        })

    leaderboard_data.sort(
        key=lambda item: (
            item["total_score"],
            item["accuracy"],
        ),
        reverse=True,
    )

    return render(
        request,
        "leaderboard.html",
        {"leaderboard": leaderboard_data},
    )
