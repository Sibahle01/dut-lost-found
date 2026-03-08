import re
from difflib import SequenceMatcher
from datetime import datetime
from app.models.item import Item
from app.models.match import Match
from app.models.notification import Notification
from app import db

class TextMatcher:
    def __init__(self):
        # Common words to ignore
        self.stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                          'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'over',
                          'under', 'between', 'out', 'off', 'down', 'than', 'then', 'than',
                          'also', 'well', 'very', 'just', 'only', 'now', 'here', 'there'}
    
    def preprocess(self, text):
        """Clean and normalize text"""
        if not text:
            return ''
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation
        words = text.split()
        words = [w for w in words if w not in self.stop_words and len(w) > 2]
        return ' '.join(words)
    
    def keyword_match_score(self, text1, text2):
        """Simple keyword matching"""
        words1 = set(self.preprocess(text1).split())
        words2 = set(self.preprocess(text2).split())
        
        if not words1 or not words2:
            return 0
            
        common = words1.intersection(words2)
        return (len(common) / max(len(words1), len(words2))) * 100
    
    def fuzzy_match_score(self, text1, text2):
        """Fuzzy string matching for similar but not identical text"""
        if not text1 or not text2:
            return 0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio() * 100
    
    def extract_identifiers(self, text):
        """Extract potential identifiers like serial numbers, barcodes, etc."""
        if not text:
            return []
        
        # Pattern for serial numbers (alphanumeric, often with hyphens)
        serial_pattern = r'\b[A-Z0-9]{4,20}\b'
        serials = re.findall(serial_pattern, text.upper())
        
        # Pattern for phone numbers (South African format)
        phone_pattern = r'0[0-9]{9}\b'
        phones = re.findall(phone_pattern, text)
        
        # Pattern for email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        return serials + phones + emails


class MatchingEngine:
    def __init__(self):
        self.text_matcher = TextMatcher()
        
        # Weights for different criteria (total = 100)
        self.weights = {
            'category': 20,      # 20% - Exact match required
            'campus': 15,         # 15% - Exact match required
            'title': 25,          # 25% - Fuzzy match
            'description': 20,    # 20% - Keyword match
            'date': 10,           # 10% - Temporal proximity
            'location': 10        # 10% - Location similarity
        }
        
        # Match thresholds
        self.thresholds = {
            'auto_notify': 85,    # Auto-notify users
            'admin_review': 70,    # Flag for admin review
            'suggest': 50         # Show in suggestions
        }
    
    def calculate_category_score(self, lost_item, found_item):
        """Category must match exactly"""
        return 100 if lost_item.category == found_item.category else 0
    
    def calculate_campus_score(self, lost_item, found_item):
        """Campus must match exactly"""
        return 100 if lost_item.campus == found_item.campus else 0
    
    def calculate_title_score(self, lost_item, found_item):
        """Title similarity score"""
        # Try fuzzy match first
        fuzzy = self.text_matcher.fuzzy_match_score(lost_item.title, found_item.title)
        
        # If fuzzy is low, try keyword match
        if fuzzy < 50:
            keyword = self.text_matcher.keyword_match_score(lost_item.title, found_item.title)
            return max(fuzzy, keyword)
        
        return fuzzy
    
    def calculate_description_score(self, lost_item, found_item):
        """Description similarity score"""
        # Extract identifiers from private verification (admin only)
        lost_ids = self.text_matcher.extract_identifiers(lost_item.private_verification or '')
        found_ids = self.text_matcher.extract_identifiers(found_item.private_verification or '')
        
        # If identifiers match, that's a strong signal
        if lost_ids and found_ids:
            common_ids = set(lost_ids).intersection(set(found_ids))
            if common_ids:
                return 100  # Identifiers match = perfect score
        
        # Otherwise, match public descriptions
        lost_public = self.text_matcher.preprocess(lost_item.public_description)
        found_public = self.text_matcher.preprocess(found_item.public_description)
        
        # Try keyword matching
        keyword_score = self.text_matcher.keyword_match_score(
            lost_item.public_description, 
            found_item.public_description
        )
        
        return keyword_score
    
    def calculate_date_score(self, lost_item, found_item):
        """Score based on date proximity"""
        if not lost_item.date_of_incident or not found_item.date_of_incident:
            return 50  # Neutral score if dates missing
        
        days_diff = abs((lost_item.date_of_incident - found_item.date_of_incident).days)
        
        if days_diff <= 1:
            return 100
        elif days_diff <= 3:
            return 80
        elif days_diff <= 7:
            return 60
        elif days_diff <= 14:
            return 40
        elif days_diff <= 30:
            return 20
        else:
            return 0
    
    def calculate_location_score(self, lost_item, found_item):
        """Score based on location similarity"""
        if not lost_item.location or not found_item.location:
            return 50
        
        # Location keywords that indicate specificity
        location_keywords = ['library', 'cafeteria', 'lab', 'room', 'office', 
                            'lecture', 'hall', 'building', 'gate', 'parking',
                            'entrance', 'exit', 'staircase', 'elevator', 'floor']
        
        lost_loc = lost_item.location.lower()
        found_loc = found_item.location.lower()
        
        # Check if locations contain similar keywords
        score = 0
        for keyword in location_keywords:
            if keyword in lost_loc and keyword in found_loc:
                score += 25
            elif keyword in lost_loc or keyword in found_loc:
                score += 10
        
        # Fuzzy match on full location text
        fuzzy = self.text_matcher.fuzzy_match_score(lost_loc, found_loc)
        
        return min(max(score, fuzzy), 100)
    
    def calculate_match_score(self, lost_item, found_item):
        """Calculate overall match score between lost and found items"""
        # Quick elimination - different categories or campuses cannot match
        if lost_item.category != found_item.category:
            return 0
        if lost_item.campus != found_item.campus:
            return 0
        
        scores = {}
        
        # Calculate individual scores
        scores['category'] = self.calculate_category_score(lost_item, found_item)
        scores['campus'] = self.calculate_campus_score(lost_item, found_item)
        scores['title'] = self.calculate_title_score(lost_item, found_item)
        scores['description'] = self.calculate_description_score(lost_item, found_item)
        scores['date'] = self.calculate_date_score(lost_item, found_item)
        scores['location'] = self.calculate_location_score(lost_item, found_item)
        
        # Calculate weighted total
        total_score = sum(
            scores[criteria] * (self.weights[criteria] / 100) 
            for criteria in self.weights
        )
        
        return {
            'total': round(total_score, 2),
            'breakdown': scores
        }
    
    def find_potential_matches(self, item, min_score=50):
        """Find all potential matches for an item above threshold"""
        if item.type == 'lost':
            # Look for found items that might match this lost item
            candidates = Item.query.filter_by(
                type='found',
                status='open',
                category=item.category,
                campus=item.campus
            ).all()
        else:
            # Look for lost items that might match this found item
            candidates = Item.query.filter_by(
                type='lost',
                status='open',
                category=item.category,
                campus=item.campus
            ).all()
        
        matches = []
        for candidate in candidates:
            if item.id == candidate.id:
                continue  # Don't match with itself
            
            # Skip if already matched
            existing_match = Match.query.filter(
                ((Match.lost_item_id == item.id) & (Match.found_item_id == candidate.id)) |
                ((Match.lost_item_id == candidate.id) & (Match.found_item_id == item.id))
            ).first()
            
            if existing_match:
                continue
            
            if item.type == 'lost':
                result = self.calculate_match_score(item, candidate)
            else:
                result = self.calculate_match_score(candidate, item)
            
            if result['total'] >= min_score:
                matches.append({
                    'item': candidate,
                    'score': result['total'],
                    'breakdown': result['breakdown'],
                    'type': 'found' if item.type == 'lost' else 'lost'
                })
        
        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches
    
    def auto_match_job(self):
        """Run automatically to find matches and create notifications"""
        from app.models.user import User
        
        # Find all unmatched found items
        found_items = Item.query.filter_by(type='found', status='open').all()
        
        notifications_created = 0
        for found in found_items:
            matches = self.find_potential_matches(found, min_score=self.thresholds['admin_review'])
            
            if matches:
                # Create a notification for admin to review
                admin = User.query.filter_by(role='admin').first()
                if admin:
                    notif = Notification(
                        user_id=admin.id,
                        related_item_id=found.id,
                        type='system_alert',
                        message=f'Auto-matcher found {len(matches)} potential matches for item {found.reference_number}',
                        channel='in_app'
                    )
                    db.session.add(notif)
                    notifications_created += 1
                
                # Auto-notify users if score is high enough
                for match in matches:
                    if match['score'] >= self.thresholds['auto_notify']:
                        # Notify the owner of the lost item
                        lost_item = match['item'] if found.type == 'found' else found
                        found_item = found if found.type == 'found' else match['item']
                        
                        notif_lost = Notification(
                            user_id=lost_item.reported_by,
                            related_item_id=lost_item.id,
                            type='match_found',
                            message=f'High-confidence match found for your lost item: {found_item.title} (Score: {match["score"]}%)',
                            channel='in_app'
                        )
                        db.session.add(notif_lost)
                        
                        notif_found = Notification(
                            user_id=found_item.reported_by,
                            related_item_id=found_item.id,
                            type='match_found',
                            message=f'Your found item may match a lost item: {lost_item.title} (Score: {match["score"]}%)',
                            channel='in_app'
                        )
                        db.session.add(notif_found)
                        notifications_created += 2
        
        db.session.commit()
        return notifications_created
