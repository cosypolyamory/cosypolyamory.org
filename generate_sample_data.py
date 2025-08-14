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
    
    # Define user distribution
    users_data = [
        # Admin (1)
        {
            'name': 'Rumpskins',
            'email': 'rump@cosypolyamory.org', 
            'role': 'admin',
            'has_application': False,
            'application_status': 'approved'
        },
        
        # Organizers (2)
        {
            'name': 'Evil-Momma',
            'email': 'kirsten@example.com',
            'role': 'organizer', 
            'has_application': True,
            'application_status': 'approved'
        },
        {
            'name': 'Alex Event-Planner',
            'email': 'alex.planner@example.com',
            'role': 'organizer',
            'has_application': True, 
            'application_status': 'approved'
        }
    ]
    
    # Generate approved members (12)
    for i in range(12):
        users_data.append({
            'name': fake.name(),
            'email': fake.unique.email(),
            'role': 'approved',
            'has_application': True,
            'application_status': 'approved'
        })
    
    # Generate pending members (8) 
    for i in range(8):
        users_data.append({
            'name': fake.name(),
            'email': fake.unique.email(), 
            'role': 'pending',
            'has_application': True,
            'application_status': 'pending'
        })
    
    # Generate users who logged in but never applied (5)
    for i in range(5):
        users_data.append({
            'name': fake.name(),
            'email': fake.unique.email(),
            'role': 'new',
            'has_application': False,
            'application_status': None
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
            last_login=fake.date_time_between(start_date='-3M', end_date='now')
        )
        
        created_users.append(user)
        
        # Create application if needed
        if user_data['has_application']:
            create_user_application(user, user_data['application_status'])
    
    print(f"   ✅ Created {len(created_users)} users")
    print(f"      - 1 admin, 2 organizers")
    print(f"      - 12 approved members")  
    print(f"      - 8 pending applications")
    print(f"      - 5 users without applications")
    
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
    
    UserApplication.create(
        user=user,
        status=status,
        question_1_answer=random.choice(sample_responses['question_1']),
        question_2_answer=random.choice(sample_responses['question_2']),
        question_3_answer=random.choice(sample_responses['question_3']),
        question_4_answer=random.choice(sample_responses['question_4']),
        question_5_answer=random.choice(sample_responses['question_5']),
        question_6_answer=random.choice(sample_responses['question_6']),
        question_7_answer=random.choice(sample_responses['question_7']),
        submitted_at=fake.date_time_between(start_date='-2M', end_date='now')
    )

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
    
    # Event types and descriptions
    event_templates = [
        {
            'title': 'Polyamory Discussion Circle',
            'description': 'A safe space to discuss experiences, challenges, and insights about polyamorous relationships. Open to all levels of experience.'
        },
        {
            'title': 'Community Social Mixer', 
            'description': 'Casual social event to meet other community members, make friends, and enjoy good conversation in a relaxed atmosphere.'
        },
        {
            'title': 'Relationship Skills Workshop',
            'description': 'Interactive workshop focusing on communication, boundary setting, and conflict resolution in polyamorous relationships.'
        },
        {
            'title': 'New Member Welcome Event',
            'description': 'Special event for new community members to meet organizers, learn about our community, and connect with welcoming faces.'
        },
        {
            'title': 'Book Club: Polyamory Literature',
            'description': 'Monthly book discussion focusing on polyamory, ethical non-monogamy, and relationship philosophy.'
        },
        {
            'title': 'Game Night & Connections',
            'description': 'Fun evening of board games, card games, and social activities. Great for breaking the ice and making new connections.'
        },
        {
            'title': 'Outdoor Picnic & Activities', 
            'description': 'Casual outdoor gathering with food, games, and activities in a beautiful Barcelona park setting.'
        },
        {
            'title': 'Communication Skills Practice',
            'description': 'Hands-on practice session for developing better communication skills specific to non-monogamous relationships.'
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
            event_date = fake.date_time_between(start_date='-3M', end_date='-1d')
        else:  # Future events
            event_date = fake.date_time_between(start_date='+1d', end_date='+3M')
        
        # Generate Google Maps link for the venue
        google_maps_link = f"https://maps.google.com/?q={venue.replace(' ', '+')},+{barrio.replace(' ', '+')},+Barcelona,+Spain"
        
        event = Event.create(
            title=template['title'],
            description=template['description'],
            organizer=organizer,
            co_host=co_host,
            date=event_date,
            exact_time=event_date,
            time_period=random.choice(time_periods),
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
    
    # Count applications
    total_apps = UserApplication.select().count()
    pending_apps = UserApplication.select().where(UserApplication.status == 'pending').count()
    approved_apps = UserApplication.select().where(UserApplication.status == 'approved').count()
    
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
