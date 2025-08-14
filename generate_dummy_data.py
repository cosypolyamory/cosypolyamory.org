#!/usr/bin/env python3
"""
Generate realistic dummy data for Cosy Polyamory application
Creates 25 users with applications and 15 events
"""

import random
from datetime import datetime, timedelta
from cosypolyamory.database import init_database
from cosypolyamory.models.user import User
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP

def generate_dummy_data():
    """Generate all dummy data"""
    print("🚀 Starting dummy data generation...")
    
    # Initialize database
    init_database()
    
    # Clear existing data (except system users)
    print("🧹 Clearing existing dummy data...")
    RSVP.delete().execute()
    Event.delete().execute()
    UserApplication.delete().where(UserApplication.user != 'system_deleted_user').execute()
    User.delete().where(User.id != 'system_deleted_user').execute()
    
    # Generate users and applications
    users = generate_users()
    generate_applications(users)
    
    # Generate events
    events = generate_events(users)
    
    # Generate RSVPs
    generate_rsvps(users, events)
    
    print("✅ Dummy data generation complete!")
    print(f"   Created {len(users)} users with realistic profiles")
    print(f"   Created {len(events)} diverse events")
    print("   Created realistic RSVPs and community interactions")
    print()
    print("📋 Summary:")
    print(f"   👥 Users: {len([u for u in users if u.role == 'approved'])} approved, {len([u for u in users if u.role == 'organizer'])} organizers, {len([u for u in users if u.role == 'pending'])} pending")
    print(f"   📅 Events: Mix of workshops, social events, and educational sessions")
    print(f"   ✅ RSVPs: Realistic attendance patterns with diverse participation")
    print()
    print("🚀 Your application is now populated with realistic test data!")

def generate_users():
    """Generate 25 realistic users"""
    print("👥 Creating users...")
    
    # Realistic user data
    user_data = [
        # Approved users (20)
        {"name": "Alex Thompson", "email": "alex.thompson@email.com", "role": "approved", "provider": "google"},
        {"name": "Sam Rodriguez", "email": "sam.rodriguez@gmail.com", "role": "approved", "provider": "google"},
        {"name": "Jordan Kim", "email": "jordan.kim@outlook.com", "role": "approved", "provider": "github"},
        {"name": "Riley Chen", "email": "riley.chen@proton.me", "role": "approved", "provider": "google"},
        {"name": "Taylor Swift", "email": "taylor.swift@email.com", "role": "approved", "provider": "google"},
        {"name": "Morgan Davis", "email": "morgan.davis@gmail.com", "role": "approved", "provider": "github"},
        {"name": "Casey Williams", "email": "casey.williams@yahoo.com", "role": "approved", "provider": "google"},
        {"name": "Avery Johnson", "email": "avery.johnson@email.com", "role": "approved", "provider": "google"},
        {"name": "Blake Anderson", "email": "blake.anderson@gmail.com", "role": "approved", "provider": "github"},
        {"name": "Quinn Martinez", "email": "quinn.martinez@proton.me", "role": "approved", "provider": "google"},
        {"name": "Sage Miller", "email": "sage.miller@email.com", "role": "approved", "provider": "google"},
        {"name": "River Garcia", "email": "river.garcia@gmail.com", "role": "approved", "provider": "github"},
        {"name": "Phoenix Wilson", "email": "phoenix.wilson@outlook.com", "role": "approved", "provider": "google"},
        {"name": "Dakota Brown", "email": "dakota.brown@email.com", "role": "approved", "provider": "google"},
        {"name": "Rowan Jones", "email": "rowan.jones@gmail.com", "role": "approved", "provider": "github"},
        {"name": "Skyler Taylor", "email": "skyler.taylor@proton.me", "role": "approved", "provider": "google"},
        {"name": "Emery White", "email": "emery.white@email.com", "role": "approved", "provider": "google"},
        {"name": "Finley Clark", "email": "finley.clark@gmail.com", "role": "approved", "provider": "github"},
        {"name": "Hayden Lewis", "email": "hayden.lewis@outlook.com", "role": "approved", "provider": "google"},
        {"name": "Jamie Parker", "email": "jamie.parker@email.com", "role": "approved", "provider": "google"},
        
        # Organizers (3)
        {"name": "Adrian Foster", "email": "adrian.foster@email.com", "role": "organizer", "provider": "google"},
        {"name": "Cameron Reed", "email": "cameron.reed@gmail.com", "role": "organizer", "provider": "github"},
        {"name": "Drew Sullivan", "email": "drew.sullivan@proton.me", "role": "organizer", "provider": "google"},
        
        # Pending applications (2)
        {"name": "Newbie Smith", "email": "newbie.smith@email.com", "role": "pending", "provider": "google"},
        {"name": "Curious Jones", "email": "curious.jones@gmail.com", "role": "pending", "provider": "github"},
    ]
    
    users = []
    avatars = [
        "https://api.dicebear.com/7.x/avataaars/svg?seed=",
        "https://api.dicebear.com/7.x/personas/svg?seed=",
        "https://api.dicebear.com/7.x/adventurer/svg?seed="
    ]
    
    for i, data in enumerate(user_data):
        # Generate realistic avatar URL
        avatar_style = random.choice(avatars)
        avatar_url = f"{avatar_style}{data['name'].replace(' ', '')}"
        
        user = User.create(
            id=f"user_{i+1:03d}",
            name=data["name"],
            email=data["email"],
            avatar_url=avatar_url,
            provider=data["provider"],
            role=data["role"]
        )
        users.append(user)
    
    print(f"   ✅ Created {len(users)} users")
    return users

def generate_applications(users):
    """Generate realistic applications for users"""
    print("📝 Creating user applications...")
    
    # Realistic application responses
    poly_experiences = [
        "I'm new to polyamory but have been researching and reading about it for about 6 months. I'm excited to learn from an experienced community.",
        "I've been practicing ethical non-monogamy for about 2 years now. Started with an open relationship and evolved into polyamory.",
        "Polyamorous for 5+ years. I have two committed partners and am comfortable with the dynamics of multiple relationships.",
        "I'm solo poly and have been for about 3 years. I value my independence while maintaining meaningful connections.",
        "New to the scene but have always felt drawn to the idea of loving multiple people. Looking for guidance and community.",
        "I've been in a polyamorous triad for 18 months. We're all learning together and want to connect with others.",
        "Experienced in poly relationships (7+ years). I enjoy mentoring newcomers and sharing knowledge.",
        "I'm questioning monogamy and exploring what ethical non-monogamy means to me. Very early in my journey.",
        "I've had several poly relationships over the past 4 years. Some worked well, others taught me valuable lessons.",
        "Been polyamorous for most of my adult life. I believe in relationship anarchy and authentic connections."
    ]
    
    english_levels = [
        "Native speaker",
        "Advanced - I'm very comfortable with English in all situations",
        "Upper Intermediate - I can express myself well but occasionally search for words",
        "Advanced - English is my second language but I'm fluent",
        "Native - Born and raised English speaker",
        "Upper Intermediate - I read and write well, speaking is good too",
        "Advanced - I work in English daily and am very comfortable"
    ]
    
    community_experiences = [
        "This would be my first polyamory community. I've been part of other social groups but nothing specifically poly.",
        "I was briefly part of a poly meetup group in another city before moving here.",
        "I've attended a few poly workshops and munches but haven't joined a regular community yet.",
        "I was active in a poly Facebook group for about a year but am looking for more in-person connection.",
        "New to poly communities entirely. Most of my learning has been through books and podcasts so far.",
        "I helped organize poly meetups in my previous city for about 2 years before relocating.",
        "I've been part of various alternative lifestyle communities but this is my first poly-specific group.",
        "I attended some poly conferences and workshops but haven't been part of a regular local community.",
        "I was in a poly community for about 6 months a few years ago. Positive experience overall.",
        "Never been part of organized poly communities but have poly friends I talk with regularly."
    ]
    
    dating_responses = [
        "I understand this is a community space, not a dating app. I'm here to build friendships and learn.",
        "The guidelines are clear - no using the group for dating. I respect that and am here for community.",
        "I know this isn't a dating service. I'm looking for genuine connections and community support.",
        "Clear that dating through the group isn't appropriate. I'm here to meet like-minded people as friends.",
        "I understand the no-dating rule and think it's important for maintaining a safe community space.",
        "The group isn't for dating - got it! I want to connect with others who share similar relationship styles.",
        "I respect that this is about community, not hookups. Looking forward to meaningful friendships."
    ]
    
    dm_responses = [
        "I understand DMs should be limited and always respectful. I'll ask before messaging anyone privately.",
        "The DM guidelines make sense for safety. I'll keep any private messages appropriate and brief.",
        "I know to be thoughtful about direct messages and always respect boundaries.",
        "DMs should be used sparingly and appropriately. I understand the importance of consent in all interactions.",
        "I'll be respectful about private messaging and understand that public group interaction is preferred.",
        "Got it on the DM etiquette - public posts when possible, private messages only when necessary and appropriate."
    ]
    
    monologue_responses = [
        "I understand this is about dialogue, not monologues. I'll keep contributions conversational and invite others to share.",
        "No dominating conversations - makes sense! I'll make sure to leave space for others to contribute.",
        "I know to avoid long monologues and keep discussions balanced. Everyone's voice matters.",
        "The anti-monologue rule is important for inclusive discussion. I'll be mindful of speaking time.",
        "I understand the importance of shared conversation rather than one person dominating discussions.",
        "Got it - keep contributions brief and always make room for others to participate in conversations."
    ]
    
    interests = [
        "I'm interested in learning about ethical communication, relationship boundaries, and building a supportive community.",
        "I'd love to discuss different polyamory styles, time management, and connecting with like-minded people.",
        "I'm hoping to learn about jealousy management, communication skills, and making friends in the community.",
        "I want to explore topics like compersion, relationship agreements, and finding my place in the poly world.",
        "I'm interested in discussions about solo poly, building chosen family, and supporting each other's growth.",
        "I hope to learn about coming out as poly, dealing with stigma, and creating authentic relationships.",
        "I'm looking forward to conversations about relationship anarchy, consent culture, and community building.",
        "I want to discuss topics like metamour relationships, time management, and navigating poly in a mono world."
    ]
    
    for user in users:
        if user.role in ['approved', 'organizer', 'pending']:
            UserApplication.create(
                user=user,
                question_1_answer=random.choice(interests),
                question_2_answer=random.choice(poly_experiences),
                question_3_answer=random.choice(english_levels),
                question_4_answer=random.choice(community_experiences),
                question_5_answer=random.choice(dating_responses),
                question_6_answer=random.choice(dm_responses),
                question_7_answer=random.choice(monologue_responses),
                status='approved' if user.role in ['approved', 'organizer'] else 'pending'
            )
    
    print(f"   ✅ Created applications for {len([u for u in users if u.role != 'deleted'])} users")

def generate_events(users):
    """Generate 15 realistic events"""
    print("📅 Creating events...")
    
    # Get organizers
    organizers = [u for u in users if u.role in ['organizer', 'admin']]
    approved_users = [u for u in users if u.role in ['approved', 'organizer']]
    
    # Event templates with realistic data
    event_templates = [
        {
            "title": "Polyamory 101: Introduction Workshop",
            "description": "A beginner-friendly workshop covering the basics of ethical non-monogamy, communication skills, and common challenges. Perfect for those new to polyamory or curious about the lifestyle. We'll cover topics like consent, jealousy, time management, and building healthy multiple relationships.",
            "time_period": "afternoon",
            "barrio": "Chueca",
            "establishment_name": "Community Center Madrid",
            "google_maps_url": "https://maps.google.com/?q=40.4214,-3.6936",
            "max_attendees": 20
        },
        {
            "title": "Poly Coffee Social",
            "description": "Casual coffee meetup for polyamorous folks to connect, chat, and share experiences in a relaxed environment. All levels of poly experience welcome! Come as you are and let's build community over good coffee and conversation.",
            "time_period": "morning",
            "barrio": "Malasaña",
            "establishment_name": "Café Central",
            "google_maps_url": "https://maps.google.com/?q=40.4267,-3.7033",
            "max_attendees": 15
        },
        {
            "title": "Communication Skills Workshop",
            "description": "Learn effective communication techniques for managing multiple relationships. We'll practice active listening, expressing needs clearly, and handling difficult conversations. Suitable for all relationship styles within ethical non-monogamy.",
            "time_period": "evening",
            "barrio": "La Latina",
            "establishment_name": "Workshop Space Madrid",
            "google_maps_url": "https://maps.google.com/?q=40.4122,-3.7089",
            "max_attendees": 18
        },
        {
            "title": "Poly Book Club: 'More Than Two'",
            "description": "Monthly book discussion focusing on Franklin Veaux and Janet Hardy's 'More Than Two'. This month we're discussing chapters 5-8 about communication and consent. Please read ahead if you plan to attend!",
            "time_period": "afternoon",
            "barrio": "Salamanca",
            "establishment_name": "Library Café",
            "google_maps_url": "https://maps.google.com/?q=40.4319,-3.6778",
            "max_attendees": 12
        },
        {
            "title": "Jealousy Management Workshop",
            "description": "A safe space to explore and discuss jealousy in polyamorous relationships. We'll cover practical strategies for managing jealousy, building compersion, and supporting your partners' other relationships.",
            "time_period": "afternoon",
            "barrio": "Centro",
            "establishment_name": "Therapy Center Madrid",
            "google_maps_url": "https://maps.google.com/?q=40.4168,-3.7038",
            "max_attendees": 16
        },
        {
            "title": "Poly Game Night",
            "description": "Fun social evening with board games, card games, and good company! A relaxed way to get to know other community members. We'll have snacks and drinks. Feel free to bring your favorite games to share!",
            "time_period": "evening",
            "barrio": "Chueca",
            "establishment_name": "Game Café Madrid",
            "google_maps_url": "https://maps.google.com/?q=40.4235,-3.6897",
            "max_attendees": 25
        },
        {
            "title": "Solo Poly Support Group",
            "description": "A discussion group specifically for solo polyamorous individuals. We'll talk about maintaining independence, setting boundaries, and thriving as a solo poly person in a couple-centric world.",
            "time_period": "evening",
            "barrio": "Malasaña",
            "establishment_name": "Coworking Space Madrid",
            "google_maps_url": "https://maps.google.com/?q=40.4289,-3.7056",
            "max_attendees": 10
        },
        {
            "title": "Poly Picnic in Retiro Park",
            "description": "Outdoor social gathering in beautiful Retiro Park! Bring a blanket, some food to share, and enjoy good weather with fellow poly community members. Great opportunity for casual conversations and making new friends.",
            "time_period": "afternoon",
            "barrio": "Retiro",
            "establishment_name": "Retiro Park",
            "google_maps_url": "https://maps.google.com/?q=40.4153,-3.6844",
            "max_attendees": 30
        },
        {
            "title": "Relationship Anarchy Discussion",
            "description": "Exploring relationship anarchy as an approach to ethical non-monogamy. We'll discuss freedom from relationship hierarchies, creating your own relationship structures, and challenging traditional relationship norms.",
            "time_period": "evening",
            "barrio": "La Latina",
            "establishment_name": "Alternative Culture Center",
            "google_maps_url": "https://maps.google.com/?q=40.4089,-3.7112",
            "max_attendees": 14
        },
        {
            "title": "New Member Welcome Meetup",
            "description": "Special welcome event for new community members! A chance to meet other newcomers, learn about our community guidelines, and ask questions in a supportive environment. Current members are welcome to help with welcoming!",
            "time_period": "afternoon",
            "barrio": "Centro",
            "establishment_name": "Community Welcome Center",
            "google_maps_url": "https://maps.google.com/?q=40.4175,-3.7026",
            "max_attendees": 20
        },
        {
            "title": "Poly Family Dynamics Workshop",
            "description": "For polyamorous people who have or want children, or who are part of poly family structures. We'll discuss co-parenting, explaining poly to children, and creating stable family environments.",
            "time_period": "afternoon",
            "barrio": "Salamanca",
            "establishment_name": "Family Center Madrid",
            "google_maps_url": "https://maps.google.com/?q=40.4342,-3.6889",
            "max_attendees": 15
        },
        {
            "title": "Metamour Relationships Panel",
            "description": "Panel discussion with experienced poly folks about building positive relationships with metamours (your partner's other partners). Tips for communication, boundaries, and creating supportive poly networks.",
            "time_period": "evening",
            "barrio": "Chueca",
            "establishment_name": "Discussion Hall",
            "google_maps_url": "https://maps.google.com/?q=40.4198,-3.6923",
            "max_attendees": 22
        },
        {
            "title": "Poly Movie Night: 'Professor Marston'",
            "description": "Movie screening and discussion of 'Professor Marston and the Wonder Women', followed by conversation about poly representation in media. Popcorn and drinks provided!",
            "time_period": "evening",
            "barrio": "Malasaña",
            "establishment_name": "Independent Cinema",
            "google_maps_url": "https://maps.google.com/?q=40.4278,-3.7089",
            "max_attendees": 18
        },
        {
            "title": "Coming Out as Poly Workshop",
            "description": "Support and practical advice for those considering coming out as polyamorous to family, friends, or colleagues. We'll discuss safety considerations, conversation strategies, and building support networks.",
            "time_period": "afternoon",
            "barrio": "Centro",
            "establishment_name": "LGBTQ+ Center Madrid",
            "google_maps_url": "https://maps.google.com/?q=40.4189,-3.7012",
            "max_attendees": 16
        },
        {
            "title": "Advanced Poly Relationships Discussion",
            "description": "For experienced polyamorous individuals looking to delve deeper into complex relationship dynamics. Topics include managing multiple serious relationships, long-term poly sustainability, and advanced communication techniques.",
            "time_period": "evening",
            "barrio": "Salamanca",
            "establishment_name": "Advanced Learning Center",
            "google_maps_url": "https://maps.google.com/?q=40.4356,-3.6812",
            "max_attendees": 12
        }
    ]
    
    events = []
    base_date = datetime.now()
    
    for i, template in enumerate(event_templates):
        # Generate realistic future dates (next 2 months)
        days_ahead = random.randint(1, 60)
        event_date = base_date + timedelta(days=days_ahead)
        
        # Set realistic times based on time_period
        if template["time_period"] == "morning":
            hour = random.choice([10, 11])
        elif template["time_period"] == "afternoon":
            hour = random.choice([14, 15, 16, 17])
        else:  # evening
            hour = random.choice([18, 19, 20])
        
        event_datetime = event_date.replace(hour=hour, minute=random.choice([0, 30]), second=0, microsecond=0)
        
        # Assign organizer and co-host
        organizer = random.choice(organizers)
        co_host = random.choice([None, None, random.choice(approved_users)])  # 2/3 chance of no co-host
        if co_host == organizer:
            co_host = None
        
        event = Event.create(
            title=template["title"],
            description=template["description"],
            date=event_datetime.replace(hour=0, minute=0, second=0, microsecond=0),  # Date only for public display
            exact_time=event_datetime,  # Exact time for approved users
            time_period=template["time_period"],
            barrio=template["barrio"],
            establishment_name=template["establishment_name"],
            google_maps_link=template["google_maps_url"],
            max_attendees=template["max_attendees"],
            organizer=organizer,
            co_host=co_host,
            is_active=True
        )
        events.append(event)
    
    print(f"   ✅ Created {len(events)} events")
    return events

def generate_rsvps(users, events):
    """Generate realistic RSVPs for events"""
    print("✅ Creating RSVPs...")
    
    approved_users = [u for u in users if u.role in ['approved', 'organizer']]
    rsvp_count = 0
    
    for event in events:
        # Determine how many people will RSVP (20-80% of max capacity)
        max_rsvps = min(len(approved_users), event.max_attendees or len(approved_users))
        num_rsvps = random.randint(int(max_rsvps * 0.2), int(max_rsvps * 0.8))
        
        # Select random users to RSVP
        rsvp_users = random.sample(approved_users, num_rsvps)
        
        for user in rsvp_users:
            # Realistic RSVP distribution: mostly yes, some no, few maybe
            status_weights = [('yes', 70), ('no', 20), ('maybe', 10)]
            status = random.choices([s[0] for s in status_weights], weights=[s[1] for s in status_weights])[0]
            
            # Add some notes for variety
            notes_options = [
                "",  # Most have no notes
                "",
                "",
                "Looking forward to this!",
                "Excited to meet everyone!",
                "First time attending, bit nervous but excited",
                "Will try to make it but might be a few minutes late",
                "Thanks for organizing this"
            ]
            
            RSVP.create(
                event=event,
                user=user,
                status=status,
                notes=random.choice(notes_options)
            )
            rsvp_count += 1
    
    print(f"   ✅ Created {rsvp_count} RSVPs")

if __name__ == "__main__":
    try:
        generate_dummy_data()
    except Exception as e:
        print(f"❌ Error generating dummy data: {e}")
        import traceback
        traceback.print_exc()
