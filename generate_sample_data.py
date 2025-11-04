#!/usr/bin/env python3
"""
Sample Data Generator for Cosy Polyamory Community
==================================================

This script generates realistic test data for development and testing purposes.
It creates users, events, applications, and RSVPs with varied statuses.

⚠️  WARNING: This will modify your database! ⚠️
"""

import os
import sys
from datetime import datetime, timedelta
import random
from faker import Faker

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cosypolyamory.database import init_database
from cosypolyamory.models.user import User
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.event_note import EventNote

def get_user_confirmation():
    """Require explicit YES confirmation before proceeding"""
    print("🔥 DATABASE WARNING 🔥")
    print("=" * 60)
    print("This script will generate sample data in your database.")
    print("This may modify or add to existing data.")
    print()
    print("Current database:", os.path.abspath(os.getenv('DB_PATH', 'cosypolyamory.db')))
    
    # Show current database contents
    try:
        user_count = User.select().count()
        event_count = Event.select().count()
        rsvp_count = RSVP.select().count()
        app_count = UserApplication.select().count()
        note_count = EventNote.select().count()
        
        print(f"Current contents: {user_count} users, {event_count} events, {rsvp_count} RSVPs, {app_count} applications, {note_count} event notes")
        
        if user_count > 0:
            print("🚨 EXISTING DATA DETECTED - This will add to existing data!")
    except Exception as e:
        print(f"Could not check current database: {e}")
    
    print()
    print("⚠️  To proceed, you must type 'YES' exactly (case sensitive)")
    print("   Any other input will abort the operation.")
    print()
    
    user_input = input("Type 'YES' to continue: ").strip()
    
    if user_input != "YES":
        print("❌ Operation cancelled. Database unchanged.")
        sys.exit(0)
    
    print("✅ Confirmation received. Proceeding with data generation...")
    print()

def clear_existing_test_data():
    """Clear existing test data (only data created by this script)"""
    print("🧹 Clearing existing test data...")
    
    try:
        # Delete sample event notes
        deleted_notes = EventNote.delete().where(
            EventNote.name.in_(["Hiking Safety & Guidelines", "Social Drinks Guidelines"])
        ).execute()
        
        # Delete test users (those with IDs starting with 'test_user_')
        test_users = User.select().where(User.id.startswith('test_user_'))
        deleted_users = 0
        
        for user in test_users:
            # Delete related RSVPs
            RSVP.delete().where(RSVP.user == user).execute()
            # Delete related applications
            UserApplication.delete().where(UserApplication.user == user).execute()
            # Delete events where this user is organizer or co-host
            Event.delete().where((Event.organizer == user) | (Event.co_host == user)).execute()
            # Delete the user
            user.delete_instance()
            deleted_users += 1
        
        print(f"   ✅ Removed {deleted_users} test users and their related data")
        if deleted_notes > 0:
            print(f"   ✅ Removed {deleted_notes} sample event notes")
        
    except Exception as e:
        print(f"   ⚠️  Error clearing test data: {e}")
        print("   Continuing with data generation...")

def create_sample_users():
    """Create a diverse set of sample users with different statuses"""
    fake = Faker()
    
    print("👥 Creating sample users...")
    
    # Define pronoun options for diversity
    pronoun_options = [
        ('they', 'them'),
        ('she', 'her'),
        ('he', 'him'),
        ('xe', 'xem'),
        ('ze', 'zir'),
        ('they', 'them'),  # More common, so appears twice
        ('she', 'her'),    # More common, so appears twice
        ('he', 'him'),     # More common, so appears twice
        (None, None),      # Some users don't specify pronouns
    ]
    
    def get_random_pronouns():
        """Get random pronouns from the options"""
        return random.choice(pronoun_options)
    
    # Define user distribution per your requirements
    users_data = []
    
    # Generate approved members (10)
    for i in range(10):
        pronouns = get_random_pronouns()
        users_data.append({
            'name': fake.name(),
            'email': fake.unique.email(),
            'role': 'approved',
            'has_application': True,
            'application_status': 'approved',
            'pronouns': f'{pronouns[0]}/{pronouns[1]}'
        })
    
    # Generate organizers (3)
    organizer_names = ['Alex Event-Planner', 'Sam Community-Builder', 'Morgan Facilitator']
    for i, name in enumerate(organizer_names):
        pronouns = get_random_pronouns()
        users_data.append({
            'name': name,
            'email': f'{name.lower().replace(" ", ".").replace("-", "")}@example.com',
            'role': 'organizer',
            'has_application': True,
            'application_status': 'approved',
            'pronouns': f'{pronouns[0]}/{pronouns[1]}'
        })
    
    # Generate pending applications (5)
    for i in range(5):
        pronouns = get_random_pronouns()
        users_data.append({
            'name': fake.name(),
            'email': fake.unique.email(),
            'role': 'pending',
            'has_application': True,
            'application_status': 'pending',
            'pronouns': f'{pronouns[0]}/{pronouns[1]}'
        })
    
    # Generate users who logged in but never applied (3)
    for i in range(3):
        pronouns = get_random_pronouns()
        users_data.append({
            'name': fake.name(),
            'email': fake.unique.email(),
            'role': 'new',
            'has_application': False,
            'application_status': None,
            'pronouns': f'{pronouns[0]}/{pronouns[1]}'
        })
    
    created_users = []
    
    for i, user_data in enumerate(users_data):
        # Create user
        user = User.create(
            id=f"test_user_{i+1:03d}",
            email=user_data['email'],
            name=user_data['name'],
            role=user_data['role'],
            provider='test',
            avatar_url=f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_data['name'].replace(' ', '')}",
            last_login=fake.date_time_between(start_date='-3M', end_date='now'),
            pronouns=user_data['pronouns']
        )
        
        created_users.append(user)
        
        # Create application if needed
        if user_data['has_application']:
            create_user_application(user, user_data['application_status'])
    
    print(f"   ✅ Created {len(created_users)} users")
    print(f"      - 0 admins")
    print(f"      - 3 organizers") 
    print(f"      - 10 approved members")  
    print(f"      - 5 pending applications")
    print(f"      - 3 users without applications")
    
    return created_users

def create_user_application(user, status):
    """Create a user application with realistic responses"""
    fake = Faker()
    
    # Sample responses for each question based on the actual application questions
    sample_responses = {
        'question_1': [  # Why interested in our group?
            "I'm new to Barcelona and looking to connect with like-minded people in the polyamory community.",
            "I've been practicing polyamory for a while and would love to meet others who share similar values.",
            "I'm interested in learning more about ethical non-monogamy in a supportive environment.",
            "I want to be part of a community where I can be open about my relationship style.",
            "I'm looking for friendship, community, and possibly romantic connections in a safe space.",
            "I've recently discovered polyamory and would like guidance from experienced practitioners.",
            "I want to attend social events where I don't have to hide my relationship orientation."
        ],
        'question_2': [  # Experience with polyamory
            "I'm completely new to polyamory but have done extensive reading and feel ready to explore.",
            "I've been practicing polyamory for about 6 months and am still learning the ropes.",
            "I've been polyamorous for 2 years and have had several meaningful relationships.",
            "I've been in open relationships before but am new to the formal polyamory community.",
            "I've been practicing ethical non-monogamy for over a year with my primary partner.",
            "I'm just starting out but have been researching polyamory for several months.",
            "I've been polyamorous for 3+ years and am experienced with multiple relationships."
        ],
        'question_3': [  # English level
            "Native",
            "Advanced",
            "Upper Intermediate", 
            "Intermediate",
            "Advanced - I'm a native Spanish speaker but very comfortable in English",
            "Upper Intermediate - I can communicate well but sometimes need clarification",
            "Advanced - English is my second language but I'm fluent"
        ],
        'question_4': [  # Previous community experience
            "No, this would be my first polyamory community but I'm excited to learn.",
            "I was part of an online polyamory forum but haven't joined an in-person group before.",
            "Yes, I was active in a poly meetup group in London before moving to Barcelona.",
            "I've attended a few polyamory workshops but haven't been part of a regular community.",
            "I was in a polyamory discussion group in my university but nothing since then.",
            "No previous formal community experience, but I have poly friends who recommended your group.",
            "I was part of a small poly social group in my previous city for about a year."
        ],
        'question_5': [  # About using group as dating service
            "The group is not a dating service but a community for support, friendship, and social connection.",
            "This is a community focused on friendship and support, not primarily for dating or hookups.",
            "The group emphasizes community building and education rather than being a dating platform.",
            "It's about creating genuine connections and community, not treating it like a dating app.",
            "The focus should be on building friendships and community first, with dating being secondary.",
            "This is a social community for polyamorous people, not a matchmaking service.",
            "The group prioritizes authentic relationships and community over casual dating."
        ],
        'question_6': [  # About direct messages
            "Direct messages should be respectful and consensual, not used for unwanted advances.",
            "DMs should be used appropriately - for logistics, genuine conversation, not for harassment.",
            "Direct messaging should respect boundaries and not be used to pressure anyone.",
            "Messages should be sent with consent and respect, following community guidelines.",
            "DMs are for appropriate communication only, not for unsolicited romantic/sexual messages.",
            "Direct messages should follow the same respect and consent rules as in-person interactions.",
            "Messaging should be consensual and respectful, not used to circumvent group boundaries."
        ],
        'question_7': [  # About monologues
            "Conversations should be balanced - listen as much as you speak and make space for others.",
            "Avoid dominating conversations; ensure everyone has a chance to participate and be heard.",
            "Long monologues can exclude others from discussion - keep contributions proportional.",
            "Be mindful of speaking time and make sure discussions remain inclusive for all participants.",
            "Conversations work best when everyone can contribute - avoid monopolizing group discussions.",
            "Share the conversational space and be aware of taking up too much time with personal stories.",
            "Group discussions should involve everyone, not become one person's extended storytelling."
        ]
    }
    
    # Create application with JSON answers
    application = UserApplication.create(
        user=user,
        submitted_at=fake.date_time_between(start_date='-2M', end_date='now')
    )
    
    # Get current questions from environment and set answers using the new format
    questions = UserApplication.get_questions_from_env()
    qa_data = {}
    
    for i, (question_key, question_text) in enumerate(questions.items(), 1):
        response_key = f'question_{i}'
        if response_key in sample_responses:
            qa_data[question_key] = {
                'question': question_text,
                'answer': random.choice(sample_responses[response_key])
            }
    
    application.set_questions_and_answers(qa_data)
    application.save()

def create_sample_events(users):
    """Create a variety of sample events"""
    fake = Faker()
    
    print("📅 Creating sample events...")
    
    # Get organizers and admin for hosting events
    organizers = [u for u in users if u.role in ['admin', 'organizer']]
    approved_users = [u for u in users if u.role == 'approved']
    
    # Barcelona neighborhoods
    neighborhoods = [
        "Gràcia", "Eixample", "Gothic Quarter", "El Born", "Poble Sec", 
        "Barceloneta", "Vila de Gràcia", "Sant Antoni", "El Raval", "Sants"
    ]
    
    # Venue types
    venues = [
        "Café Central", "Bar Luna", "Restaurant Mediterrani", "Pub The Corner",
        "Terrace Rooftop", "Bistro Garden", "Wine Bar Vintage", "Cocktail Lounge",
        "Community Center", "Park Pavilion", "Art Gallery", "Bookstore Café"
    ]
    
    # Time periods
    time_periods = [
        "Morning", "Afternoon", "Evening", "Late Evening"
    ]
    
    def get_rounded_time():
        """Generate event times rounded to 15 minutes, mostly after 19:00"""
        # 80% chance of evening events (19:00-23:00), 20% chance of earlier times
        if random.random() < 0.8:
            # Evening events (19:00 - 23:00)
            hour = random.choice([19, 19, 20, 20, 21, 21, 22])  # Weighted towards 19-21
        else:
            # Earlier events (10:00 - 18:00)
            hour = random.choice([10, 11, 12, 14, 15, 16, 17, 18])
        
        # Round minutes to 15-minute intervals
        minute = random.choice([0, 15, 30, 45])
        
        return hour, minute
    
    def calculate_end_time(start_hour, start_minute):
        """Calculate end time based on event type, typically 2-3 hours duration"""
        duration_hours = random.choice([2, 2, 2.5, 3])  # Most events 2 hours, some longer
        
        # Convert to minutes for easier calculation
        start_total_minutes = start_hour * 60 + start_minute
        duration_minutes = int(duration_hours * 60)
        end_total_minutes = start_total_minutes + duration_minutes
        
        # Convert back to hours and minutes
        end_hour = (end_total_minutes // 60) % 24  # Handle midnight wraparound
        end_minute = end_total_minutes % 60
        
        # Round end time to nearest 15 minutes
        if end_minute % 15 != 0:
            end_minute = ((end_minute // 15) + 1) * 15
            if end_minute >= 60:
                end_minute = 0
                end_hour = (end_hour + 1) % 24
        
        return end_hour, end_minute
    
    def get_time_period(hour):
        """Get appropriate time period based on hour"""
        if hour < 12:
            return "Morning"
        elif hour < 17:
            return "Afternoon"
        elif hour < 21:
            return "Evening"
        else:
            return "Late Evening"
    
    # Event types and descriptions
    event_templates = [
        {
            'title': 'Polyamory Discussion Circle',
            'description': '💬 Join us for a thoughtful and supportive discussion circle where we explore the many facets of polyamorous living. This monthly gathering provides a safe, judgement-free space for community members to share their experiences, challenges, and insights about navigating multiple relationships.\n\n🌈 Whether you\'re new to polyamory, have been practicing for years, or are simply curious about ethical non-monogamy, everyone is welcome to participate in these enriching conversations. Topics often include managing jealousy, communication strategies, time management across multiple relationships, dealing with societal judgment, building chosen family structures, and celebrating the unique joys that polyamory can bring.\n\n🤝 Our discussions are guided by principles of respect, confidentiality, and mutual support. We encourage active listening, thoughtful questions, and the sharing of both struggles and successes. Past sessions have covered themes like compersion (finding joy in your partner\'s other relationships), metamour relationships, coming out to family and friends, and creating sustainable relationship agreements.\n\n☕ Light refreshments are provided, and we always end with a circle of appreciation where participants can acknowledge something they learned or appreciated during our time together.'
        },
        {
            'title': 'Community Social Mixer', 
            'description': '🎉 Come join us for a relaxed and welcoming social gathering designed to bring our polyamory community together in a fun, low-pressure environment. This casual mixer is perfect for meeting new faces, reconnecting with familiar friends, and building the social connections that make our community strong.\n\n🎯 The event features a mix of structured activities and free-form socializing, ensuring there\'s something comfortable for everyone, whether you\'re outgoing or more introverted. We\'ll have conversation starter games, small group discussions on light topics, and plenty of opportunities for organic mingling. The venue provides a cozy atmosphere with comfortable seating areas, background music, and a variety of refreshments including both alcoholic and non-alcoholic options.\n\n🎲 Past mixers have included activities like "two truths and a lie," speed friending rounds, and collaborative art projects. We always have community organizers present to help facilitate introductions and ensure everyone feels welcome. This event is particularly great for newcomers who want to get a feel for our community culture, as well as established members looking to expand their social circle.\n\n🌟 Whether you come alone or with partners, you\'ll leave with new connections and a stronger sense of belonging to our polyamory community. We ask all attendees to be respectful of boundaries and remember that this is a social event, not specifically a dating opportunity.'
        },
        {
            'title': 'Relationship Skills Workshop',
            'description': '🛠️ Dive deep into the essential skills that make polyamorous relationships thrive in this comprehensive, hands-on workshop. Led by experienced community members and occasionally guest facilitators with backgrounds in relationship counseling or psychology, this interactive session focuses on practical tools and techniques that can be immediately applied to your relationship dynamics.\n\n📚 The workshop covers a wide range of crucial topics including advanced communication strategies, effective boundary setting and negotiation, conflict resolution techniques specific to multi-partner dynamics, and emotional regulation skills. Participants will engage in role-playing exercises, small group discussions, and individual reflection activities designed to help integrate these concepts into their daily relationship practices.\n\n🎭 We explore challenging scenarios like managing scheduling conflicts, addressing jealousy constructively, navigating different relationship styles within your polycule, and maintaining individual identity within multiple partnerships. The workshop also delves into topics like consent culture, emotional labor distribution, and creating sustainable agreements that evolve with your relationships.\n\n📋 Attendees receive practical worksheets, reference materials, and follow-up resources to continue their learning journey. The format is highly interactive, encouraging participants to share their experiences and learn from each other\'s perspectives. We maintain a supportive, non-judgmental atmosphere where questions are welcomed and vulnerability is honored.'
        },
        {
            'title': 'New Member Welcome Event',
            'description': '🤗 Step into our community with confidence at this special orientation event designed specifically for newcomers to both polyamory and our local community group. This welcoming gathering provides a comprehensive introduction to who we are, what we stand for, and how you can get involved in our vibrant community.\n\n📖 The event begins with a warm welcome from our organizing team, followed by an overview of our community\'s history, values, and guidelines for participation. New members will learn about our various types of events, ongoing programs, and the many ways to connect and contribute. We\'ll cover practical information like how to RSVP for events, our community communication channels, and resources for continued learning about polyamory and ethical non-monogamy.\n\n💭 A significant portion of the event is dedicated to small group discussions where newcomers can ask questions, share their backgrounds, and begin forming connections with both other newcomers and established community members who serve as welcoming ambassadors. These conversations often touch on topics like what brought people to polyamory, their hopes for community involvement, and any concerns or curiosities they might have.\n\n📦 We provide information packets with recommended reading, local resources, and contact information for ongoing support. The atmosphere is deliberately casual and supportive, with refreshments and comfortable seating arrangements that encourage natural conversation. By the end of the event, newcomers will have a clear understanding of how to engage with our community and several new connections to help them feel at home.'
        },
        {
            'title': 'Book Club: Polyamory Literature',
            'description': '📚 Expand your understanding of polyamory, ethical non-monogamy, and relationship diversity through our monthly book club that explores both classic and contemporary literature on these topics. Each month, we select a thought-provoking book that offers insights into different aspects of non-monogamous living, from practical guides to philosophical explorations to personal memoirs.\n\n🧠 Our discussions are rich, nuanced, and designed to help participants integrate new concepts into their own relationship practices and worldviews. Recent selections have included foundational texts like "The Ethical Slut" and "More Than Two," as well as newer works exploring topics like relationship anarchy, solo poly, and intersectional perspectives on non-monogamy. We also occasionally read fiction that thoughtfully portrays polyamorous characters and relationships, or academic works that examine non-monogamy from sociological, psychological, or anthropological perspectives.\n\n💡 The discussion format encourages critical thinking, personal reflection, and respectful dialogue about different viewpoints presented in the readings. Participants often share how the book\'s concepts relate to their own experiences, challenges they\'ve faced, or insights they\'ve gained. We provide discussion guides and questions to help focus our conversations, but the dialogue naturally evolves based on what resonates most with the group.\n\n🍪 The book club serves as both an educational opportunity and a way to build deeper connections within our community through shared learning. Light snacks and beverages are provided, and we often end with recommendations for additional reading or resources related to the month\'s topic.'
        },
        {
            'title': 'Game Night & Connections',
            'description': '🎮 Unwind and connect with fellow community members through the universal language of games at our monthly game night that combines fun, laughter, and meaningful social interaction. This event offers a perfect blend of structured activity and casual socializing, making it ideal for both newcomers who appreciate having something to do with their hands while getting to know people, and established members looking for a relaxed way to strengthen community bonds.\n\n🃏 We provide a diverse selection of games suitable for various group sizes and interests, including cooperative board games that encourage teamwork, party games that spark laughter and conversation, strategy games for those who enjoy mental challenges, and card games that are easy to learn and play. Popular choices have included Codenames, Ticket to Ride, Wavelength, and various social deduction games that get everyone talking and laughing together.\n\n🎲 The evening typically starts with mixer games designed to help people form groups and find compatible gaming partners, then transitions into multiple simultaneous game sessions where participants can move between tables and try different games throughout the night. We always have community members available to teach new games and help facilitate smooth group formation.\n\n🍕 The atmosphere is deliberately inclusive and welcoming, with an emphasis on fun rather than competition. Light snacks, soft drinks, and often some homemade treats are provided to keep energy levels up throughout the evening. We often see new connections and even play groups form organically through these events, extending the community building beyond the official game night itself.'
        },
        {
            'title': 'Outdoor Picnic & Activities', 
            'description': '🌳 Embrace the beautiful Barcelona weather and strengthen community connections at our seasonal outdoor gatherings held in some of the city\'s most scenic parks and green spaces. These picnic events combine the relaxed atmosphere of a casual outdoor meal with organized activities that encourage interaction, play, and community building in a natural setting.\n\n🥪 We typically choose locations that offer a mix of open spaces for games, shaded areas for conversation, and beautiful surroundings that showcase Barcelona\'s outdoor beauty. The event usually begins with a collaborative potluck-style meal where community members contribute dishes to share, creating a diverse and delicious spread that reflects our community\'s varied backgrounds and culinary traditions.\n\n⚽ After the communal meal, we organize a variety of activities designed to accommodate different interests and energy levels. These might include frisbee games, nature walks for smaller conversation groups, outdoor yoga sessions, collaborative art projects, or even educational nature activities that help us learn about local flora and fauna. We always bring supplies for various games and activities, but participants are encouraged to bring their own favorite outdoor games or activity suggestions.\n\n👨‍👩‍👧‍👦 The informal structure allows for natural group formation and reformation throughout the day, giving people opportunities to connect with different community members in various settings. Families with children are always welcome, and we typically include some family-friendly activities in our planning. The event serves as a wonderful opportunity for community members to see each other in a different context and create lasting memories in a relaxed, pressure-free environment.'
        },
        {
            'title': 'Communication Skills Practice',
            'description': '🗣️ Develop and refine the communication skills that are essential for successful polyamorous relationships through this practical, hands-on practice session that goes beyond theory to provide real-world application opportunities. This workshop-style event is designed around active participation, role-playing exercises, and guided practice of specific communication techniques that are particularly relevant to non-monogamous relationship dynamics.\n\n🎬 Participants work through common challenging scenarios that many polyamorous people face, such as discussing new relationship interests with existing partners, navigating scheduling conflicts, expressing needs and boundaries clearly, addressing jealousy and insecurity, and having difficult conversations about relationship changes. The session is facilitated by experienced community members who guide participants through various communication frameworks and techniques.\n\n💪 We practice both verbal and non-verbal communication skills, exploring how body language, tone, and timing all impact the effectiveness of our interactions. Small group exercises allow participants to work through scenarios in a supportive environment, with opportunities to try different approaches and receive gentle feedback from peers. We also explore communication challenges specific to polyamory, such as how to communicate effectively with metamours and ways to include all partners in important decisions.\n\n🌱 The practice sessions are designed to be safe and supportive, with clear guidelines about confidentiality and respect for all participants. Throughout the event, we emphasize that communication is a skill that requires ongoing practice and development, and we provide resources for continued learning and improvement. Participants often leave with specific techniques they can immediately implement in their relationships.'
        }
    ]
    
    created_events = []
    
    # Create 15 diverse events
    for i in range(15):
        template = random.choice(event_templates)
        organizer = random.choice(organizers)
        co_host = random.choice(approved_users) if random.random() > 0.6 else None
        venue = random.choice(venues)
        barrio = random.choice(neighborhoods)
        
        # Mix of past and future events
        if i < 7:  # Past events
            base_date = fake.date_between(start_date='-3M', end_date='-1d')
        else:  # Future events
            base_date = fake.date_between(start_date='+1d', end_date='+3M')
        
        # Generate realistic start and end times
        start_hour, start_minute = get_rounded_time()
        end_hour, end_minute = calculate_end_time(start_hour, start_minute)
        
        # Create datetime objects for exact times
        exact_start_time = datetime.combine(base_date, datetime.min.time().replace(hour=start_hour, minute=start_minute))
        exact_end_time = datetime.combine(base_date, datetime.min.time().replace(hour=end_hour, minute=end_minute))
        
        # Handle end time going into next day
        if end_hour < start_hour or (end_hour == start_hour and end_minute < start_minute):
            exact_end_time += timedelta(days=1)
        
        # Get appropriate time period
        time_period = get_time_period(start_hour)
        
        # Generate Google Maps link for the venue
        google_maps_link = f"https://maps.google.com/?q={venue.replace(' ', '+')},+{barrio.replace(' ', '+')},+Barcelona,+Spain"
        
        event = Event.create(
            title=template['title'],
            description=template['description'],
            organizer=organizer,
            co_host=co_host,
            date=exact_start_time,
            exact_time=exact_start_time,
            end_time=exact_end_time,  # Add end time
            time_period=time_period,
            establishment_name=venue,
            barrio=barrio,
            google_maps_link=google_maps_link,
            max_attendees=random.randint(12, 25),
            is_active=True
        )
        
        created_events.append(event)
    
    print(f"   ✅ Created {len(created_events)} events")
    print(f"      - 7 past events, 8 upcoming events")
    print(f"      - Mix of workshops, socials, and discussion groups")
    print(f"      - Most events after 19:00, times rounded to 15-minute intervals")
    print(f"      - All events have end times (typically 2-3 hours duration)")
    
    return created_events

def create_sample_rsvps(users, events):
    """Create realistic RSVP patterns for events"""
    print("🎟️  Creating sample RSVPs...")
    
    # Only approved and organizer users can RSVP
    eligible_users = [u for u in users if u.role in ['approved', 'organizer', 'admin']]
    
    total_rsvps = 0
    
    for event in events:
        # Determine RSVP count based on event type and timing
        if event.exact_time < datetime.now():  # Past events
            rsvp_rate = random.uniform(0.7, 0.9)  # Higher attendance for past events
        else:  # Future events
            rsvp_rate = random.uniform(0.4, 0.7)  # Lower current RSVPs for future events
        
        num_rsvps = int(len(eligible_users) * rsvp_rate)
        rsvp_users = random.sample(eligible_users, num_rsvps)
        
        for user in rsvp_users:
            # RSVP status distribution
            status_weights = {
                'yes': 0.6,
                'maybe': 0.25, 
                'no': 0.15
            }
            
            status = random.choices(
                list(status_weights.keys()), 
                weights=list(status_weights.values())
            )[0]
            
            RSVP.create(
                user=user,
                event=event,
                status=status,
                created_at=datetime.now() - timedelta(days=random.randint(1, 30))
            )
            
            total_rsvps += 1
    
    print(f"   ✅ Created {total_rsvps} RSVPs")
    print(f"      - Realistic attendance patterns")
    print(f"      - Mix of yes/maybe/no responses")

def display_summary():
    """Display a summary of generated data"""
    print("\n📊 DATA GENERATION SUMMARY")
    print("=" * 50)
    
    # Count users by role
    user_counts = {}
    for role in ['admin', 'organizer', 'approved', 'pending', 'new']:
        count = User.select().where(User.role == role).count()
        user_counts[role] = count
    
    print(f"👥 Users: {sum(user_counts.values())} total")
    for role, count in user_counts.items():
        print(f"   - {role.title()}: {count}")
    
    # Count events
    total_events = Event.select().count()
    past_events = Event.select().where(Event.exact_time < datetime.now()).count()
    future_events = total_events - past_events
    
    print(f"📅 Events: {total_events} total")
    print(f"   - Past: {past_events}")
    print(f"   - Upcoming: {future_events}")
    
    # Count RSVPs
    total_rsvps = RSVP.select().count()
    yes_rsvps = RSVP.select().where(RSVP.status == 'yes').count()
    maybe_rsvps = RSVP.select().where(RSVP.status == 'maybe').count()
    no_rsvps = RSVP.select().where(RSVP.status == 'no').count()
    
    print(f"🎟️  RSVPs: {total_rsvps} total")
    print(f"   - Yes: {yes_rsvps}")
    print(f"   - Maybe: {maybe_rsvps}")
    print(f"   - No: {no_rsvps}")
    
    # Count applications by user role instead of application status
    total_apps = UserApplication.select().count()
    pending_apps = (UserApplication.select()
                   .join(User)
                   .where(User.role.in_(['pending', 'new']))
                   .count())
    approved_apps = (UserApplication.select()
                    .join(User)
                    .where(User.role == 'approved')
                    .count())
    
    print(f"📋 Applications: {total_apps} total")
    print(f"   - Pending: {pending_apps}")
    print(f"   - Approved: {approved_apps}")
    
    # Count event notes
    total_notes = EventNote.select().count()
    print(f"📝 Event Notes: {total_notes} total")

def create_sample_event_notes():
    """Create sample event notes with useful information"""
    print("📝 Creating sample event notes...")
    
    # Hiking Event Note
    hiking_note = EventNote.create(
        name="Hiking Safety & Guidelines",
        note="""🥾 **Hiking Event Guidelines**

**What to Bring:**
• Comfortable hiking shoes with good grip
• Water bottle (at least 1L per person)
• Snacks or light lunch
• Weather-appropriate clothing (layers recommended)
• Small backpack
• Sunscreen and hat
• Personal first aid items if needed

**Safety Guidelines:**
• Stay with the group - don't wander off alone
• Inform the organizer of any medical conditions or limitations
• Check weather conditions before departure
• Let someone know your expected return time
• Follow Leave No Trace principles

**Meeting Point:**
We'll meet at the specified location 15 minutes before departure time. Please arrive on time as we'll brief everyone about the route and safety considerations.

**Difficulty Level:**
This hike is suitable for beginners to intermediate levels. Total duration is approximately 3-4 hours including breaks.

**Weather Policy:**
In case of heavy rain or dangerous weather conditions, the event may be cancelled. Check for updates 2 hours before the event."""
    )
    
    # Drinks Event Note
    drinks_note = EventNote.create(
        name="Social Drinks Guidelines",
        note="""🍻 **Social Drinks Event Guidelines**

**Code of Conduct Reminder:**
This is a community event where our full Code of Conduct applies. Please review it before attending. Key points:

• **Consent is Essential:** Always ask before physical contact, respect boundaries
• **Inclusive Environment:** Welcome people of all backgrounds, experiences, and identities  
• **No Harassment:** Zero tolerance for unwanted advances, inappropriate comments, or discriminatory behavior
• **Respect Privacy:** Don't share personal information or photos without permission

**Event Logistics:**
• Arrive on time - we'll have reserved seating
• Each person covers their own drinks and food
• Please drink responsibly and know your limits
• Designated meeting spot will be shared 1 hour before event

**Creating Connections:**
• Be open to meeting new people
• Include others in conversations
• Respect that not everyone may want to socialize the same way
• Exchange contact info consensually

**Safety:**
• Look out for fellow community members
• Report any concerns to organizers immediately
• Plan your transportation home in advance
• Stay hydrated and eat something if drinking

Remember: This is about building community connections in a safe, respectful environment. Let's make everyone feel welcome! 🌟"""
    )
    
    print(f"   ✅ Created 2 event notes:")
    print(f"      - {hiking_note.name}")
    print(f"      - {drinks_note.name}")
    
    return [hiking_note, drinks_note]

def main():
    """Main execution function"""
    print("🌟 COSY POLYAMORY SAMPLE DATA GENERATOR")
    print("=" * 50)
    print()
    
    try:
        # Initialize database first
        print("🗄️  Initializing database...")
        init_database()
        print("   ✅ Database ready")
        print()
        
        # Require explicit confirmation (with database status)
        get_user_confirmation()
        
        # Clear existing test data
        clear_existing_test_data()
        print()
        
        # Generate sample data
        event_notes = create_sample_event_notes()
        print()
        
        users = create_sample_users()
        print()
        
        events = create_sample_events(users)
        print()
        
        create_sample_rsvps(users, events)
        print()
        
        # Display summary
        display_summary()
        
        print("\n🎉 SAMPLE DATA GENERATION COMPLETE!")
        print("=" * 50)
        print("Your database now contains realistic test data for development.")
        print("You can start the application and explore the features!")
        
    except Exception as e:
        print(f"\n❌ Error during data generation: {e}")
        print("Database may be in an incomplete state.")
        sys.exit(1)

if __name__ == "__main__":
    main()
