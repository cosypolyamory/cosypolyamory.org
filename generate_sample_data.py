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
        
        print(f"Current contents: {user_count} users, {event_count} events, {rsvp_count} RSVPs, {app_count} applications")
        
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
            'name': 'Kirsten Organizer',
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
            create_user_application(user, user_data['application_status'], fake)
    
    print(f"   ✅ Created {len(created_users)} users")
    print(f"      - 1 admin, 2 organizers")
    print(f"      - 12 approved members")  
    print(f"      - 8 pending applications")
    print(f"      - 5 users without applications")
    
    return created_users

def create_user_application(user, status, fake):
    """Create a realistic user application"""
    
    # Sample application responses
    sample_responses = {
        'about_yourself': [
            "I'm a software developer interested in ethical non-monogamy and building meaningful connections.",
            "I work in healthcare and am exploring polyamory after ending a long-term monogamous relationship.", 
            "I'm an artist and writer who believes in authentic communication and consensual relationships.",
            "I'm a teacher who has been practicing polyamory for 2 years and looking for community.",
            "I work in tech and am new to polyamory but excited to learn and connect with like-minded people."
        ],
        'why_join': [
            "I want to connect with other polyamorous people and learn from experienced practitioners.",
            "I'm looking for a supportive community where I can be open about my relationship style.",
            "I'd like to attend events and meet people who understand non-monogamy.",
            "I want to learn more about polyamory and meet potential partners in a respectful environment.",
            "I'm seeking community, friendship, and possibly romantic connections."
        ],
        'experience_polyamory': [
            "I've been practicing polyamory for about 6 months and am still learning.",
            "I've been in open relationships before but am new to the polyamory community.",
            "I've been polyamorous for 2 years and have had a few meaningful relationships.",
            "I'm completely new but have done a lot of reading and feel ready to explore.",
            "I've been practicing ethical non-monogamy for over a year."
        ],
        'community_guidelines': [
            "Yes, I've read and agree to follow all community guidelines and the code of conduct.",
            "I understand and agree to the community standards and will respect all members.",
            "Yes, I commit to following the guidelines and creating a safe space for everyone."
        ]
    }
    
    UserApplication.create(
        user=user,
        status=status,
        about_yourself=random.choice(sample_responses['about_yourself']),
        why_join=random.choice(sample_responses['why_join']), 
        experience_polyamory=random.choice(sample_responses['experience_polyamory']),
        community_guidelines_agreement=random.choice(sample_responses['community_guidelines']),
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
