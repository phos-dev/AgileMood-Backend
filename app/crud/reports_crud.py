from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, case

from app.schemas.emotion_record_schema import EmotionRecord, Emotion
from app.schemas.team_schema import user_teams
from app.schemas.user_schema import User

from app.models.reports_model import EmojiDistributionReport, EmojiDistribution


def get_emoji_distribution_report(db: Session, team_id: int, start_date: str | None, end_date: str | None):
    filters = build_emotion_filter(team_id, start_date, end_date)
    query = (
        select(
            Emotion.name,
            func.count(EmotionRecord.id).label('frequency'),
            func.sum(case((Emotion.is_negative, 1), else_=0)).label('negative_count')
        )
        .join(EmotionRecord, EmotionRecord.emotion_id == Emotion.id)
        .where(and_(*filters))
        .group_by(Emotion.emoji, Emotion.name)
        .order_by(func.count(EmotionRecord.id).desc())
    )

    result = db.execute(query).mappings().all()

    total_records = sum(row["frequency"] for row in result)
    total_negatives = sum(row["negative_count"] for row in result)
    negative_emotion_ratio = (total_negatives / total_records) * 100 if total_records > 0 else 0

    alert = get_alert_message(negative_emotion_ratio)

    return EmojiDistributionReport(
        emoji_distribution=[EmojiDistribution(emotion_name=row["name"], frequency=row["frequency"]) for row in result],
        negative_emotion_ratio=negative_emotion_ratio,
        alert=alert,
    )


def get_average_intensity_report(db: Session, team_id: int, start_date: str | None, end_date: str | None):
    filters = build_emotion_filter(team_id, start_date, end_date)
    query = (
        select(
            Emotion.emoji,
            Emotion.name,
            func.avg(EmotionRecord.intensity).label('avg_intensity'),
            func.sum(case((Emotion.is_negative, 1), else_=0)).label('negative_count'),
            func.count(EmotionRecord.id).label('total_count')
        )
        .join(EmotionRecord, EmotionRecord.emotion_id == Emotion.id)
        .where(and_(*filters))
        .group_by(Emotion.emoji, Emotion.name)
        .order_by(func.avg(EmotionRecord.intensity).desc())
    )

    result = db.execute(query).mappings().all()

    total_records = sum(row["total_count"] for row in result)
    total_negatives = sum(row["negative_count"] for row in result)
    negative_emotion_ratio = (total_negatives / total_records) * 100 if total_records > 0 else 0

    alert = get_alert_message(negative_emotion_ratio)

    return {
        "average_intensity": [
            {"emoji": row["emoji"], "emotion_name": row["name"], "avg_intensity": float(row["avg_intensity"])}
            for row in result
        ],
        "negative_emotion_ratio": negative_emotion_ratio,
        "alert": alert
    }


def get_emotion_analysis_by_user(
        db: Session,
        team_id: int,
        user_id: int,
        start_date: str | None = None,
        end_date: str | None = None
):
    """
    Generates a report of emotions for a specific user within a specific team.
    
    Args:
        db (Session): Database session.
        team_id (int): ID of the team.
        user_id (int): ID of the user.
        start_date (str | None): Start date to filter records (format 'YYYY-MM-DD').
        end_date (str | None): End date to filter records (format 'YYYY-MM-DD').
    
    Returns:
        List[Dict]: List of dictionaries containing the user's name, recorded emotions,
                    frequency of each emotion, and average intensity.
    """

    # Executing the query
    rows = db.execute((
        select(
            User.name.label("user_name"),        # User's name
            Emotion.name.label("emotion_name"),  # Emotion's name
            Emotion.emoji,                       # Emotion's emoji
            func.count(EmotionRecord.id).label("frequency"),  # Frequency of the emotion
            func.avg(EmotionRecord.intensity).label("average_intensity")  # Average intensity
        )
        .join(EmotionRecord, EmotionRecord.user_id == User.id)
        .join(Emotion, EmotionRecord.emotion_id == Emotion.id)
        .join(user_teams, User.id == user_teams.c.user_id)
        .where(
            and_(
                user_teams.c.team_id == team_id,
                User.id == user_id,
                EmotionRecord.is_anonymous == False,
                EmotionRecord.created_at >= start_date if start_date else True,
                EmotionRecord.created_at <= end_date if end_date else True
            )
        )
        .group_by(User.name, Emotion.name, Emotion.emoji)
        .order_by(User.name, func.count(EmotionRecord.id).desc())
    )).all()

    if not rows:
        return {"user_name": "Unknown", "all_user_emotion_records": []}

    result = {"user_name": rows[0].user_name, "all_user_emotion_records": []}
    for row in rows:
        result["all_user_emotion_records"].append({
            "emotion_name": row.emotion_name,
            "emoji": row.emoji,
            "frequency": row.frequency,
            "avg_intensity": round(float(row.average_intensity), 2)
        })

    return result


def get_anonymous_emotion_analysis(
        db: Session,
        team_id: int,
        start_date: str | None = None,
        end_date: str | None = None
):
    """
    Generates a report of anonymous emotions within a specific team.
    
    Args:
        db (Session): Database session.
        team_id (int): ID of the team.
        start_date (str | None): Start date to filter records (format 'YYYY-MM-DD').
        end_date (str | None): End date to filter records (format 'YYYY-MM-DD').
    
    Returns:
        Dict: A dictionary containing the anonymous emotions recorded,
              their frequency, and average intensity.
    """

    # Executing the query
    rows = db.execute((
        select(
            Emotion.name.label("emotion_name"),    # Emotion's name
            Emotion.emoji,                        # Emotion's emoji
            func.count(EmotionRecord.id).label("frequency"),  # Frequency of the emotion
            func.avg(EmotionRecord.intensity).label("average_intensity")  # Average intensity
        )
        .select_from(EmotionRecord)
        .join(Emotion, EmotionRecord.emotion_id == Emotion.id)
        .where(
            and_(
                EmotionRecord.is_anonymous == True,
                Emotion.team_id == team_id,
                EmotionRecord.created_at >= start_date if start_date else True,
                EmotionRecord.created_at <= end_date if end_date else True
            )
        )
        .group_by(Emotion.name, Emotion.emoji)
        .order_by(func.count(EmotionRecord.id).desc())
    )).all()

    result = {"user_name": "Anonymous", "all_user_emotion_records": []}
    for row in rows:
        result["all_user_emotion_records"].append({
            "emotion_name": row.emotion_name,
            "emoji": row.emoji,
            "frequency": row.frequency,
            "avg_intensity": round(float(row.average_intensity), 2)
        })

    return result


def build_emotion_filter(team_id: int, start_date: str | None, end_date: str | None):
    filters = [Emotion.team_id == team_id]

    if start_date and end_date:
        filters.append(EmotionRecord.created_at.between(start_date, end_date))
    elif start_date:
        filters.append(EmotionRecord.created_at >= start_date)
    elif end_date:
        filters.append(EmotionRecord.created_at <= end_date)

    return filters


def get_alert_message(negative_emotion_ratio: float) -> str | None:
    if negative_emotion_ratio > 50:
        return "Crítico: Metade das emoções registradas são negativas!"

    if negative_emotion_ratio > 30:
        return "Atenção: Um pouco menos da metade das emoções registradas são negativas!"

    if negative_emotion_ratio > 15:
        return "Observação: Algumas das emoções registradas pelos colaboradores são negativas!"

    return None