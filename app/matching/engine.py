from datetime import datetime
from app import db
from app.models.item import Item
from app.models.match import Match
from app.models.notification import Notification
from app.models.user import User
import re
from difflib import SequenceMatcher

class TextMatcher:
    def __init__(self):
        self.stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                          'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'over',
                          'under', 'between', 'out', 'off', 'down', 'than', 'then', 'than',
                          'also', 'well', 'very', 'just', 'only', 'now', 'here', 'there'}
    
    def preprocess(self, text):
        if not text:
            return ''
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        words = [w for w in words if w not in self.stop_words and len(w) > 2]
        return ' '.join(words)
    
    def keyword_match_score(self, text1, text2):
        words1 = set(self.preprocess(text1).split())
        words2 = set(self.preprocess(text2).split())
        if not words1 or not words2:
            return 0
        common = words1.intersection(words2)
        return (len(common) / max(len(words1), len(words2))) * 100
    
    def fuzzy_match_score(self, text1, text2):
        if not text1 or not text2:
            return 0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio() * 100

class MatchingEngine:
    def __init__(self):
        self.text_matcher = TextMatcher()
        self.weights = {
            'category': 20,
            'campus': 15,
            'title': 25,
            'description': 20,
            'date': 10,
            'location': 10
        }
        self.thresholds = {
            'auto_notify': 85,
            'admin_review': 70,
            'suggest': 50
        }
    
    def calculate_category_score(self, lost_item, found_item):
        return 100 if lost_item.category == found_item.category else 0
    
    def calculate_campus_score(self, lost_item, found_item):
        return 100 if lost_item.campus == found_item.campus else 0
    
    def calculate_title_score(self, lost_item, found_item):
        fuzzy = self.text_matcher.fuzzy_match_score(lost_item.title, found_item.title)
        if fuzzy < 50:
            keyword = self.text_matcher.keyword_match_score(lost_item.title, found_item.title)
            return max(fuzzy, keyword)
        return fuzzy
    
    def calculate_description_score(self, lost_item, found_item):
        return self.text_matcher.keyword_match_score(
            lost_item.public_description, 
            found_item.public_description
        )
    
    def calculate_date_score(self, lost_item, found_item):
        if not lost_item.date_of_incident or not found_item.date_of_incident:
            return 50
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
        if not lost_item.location or not found_item.location:
            return 50
        return self.text_matcher.fuzzy_match_score(lost_item.location, found_item.location)
    
    def calculate_match_score(self, lost_item, found_item):
        if lost_item.category != found_item.category:
            return 0
        if lost_item.campus != found_item.campus:
            return 0
        
        scores = {
            'category': self.calculate_category_score(lost_item, found_item),
            'campus': self.calculate_campus_score(lost_item, found_item),
            'title': self.calculate_title_score(lost_item, found_item),
            'description': self.calculate_description_score(lost_item, found_item),
            'date': self.calculate_date_score(lost_item, found_item),
            'location': self.calculate_location_score(lost_item, found_item)
        }
        
        total_score = sum(
            scores[criteria] * (self.weights[criteria] / 100) 
            for criteria in self.weights
        )
        
        return {
            'total': round(total_score, 2),
            'breakdown': scores
        }
    
    def find_potential_matches(self, item, min_score=50):
        if item.type == 'lost':
            candidates = Item.query.filter_by(
                type='found', status='open',
                category=item.category, campus=item.campus
            ).all()
        else:
            candidates = Item.query.filter_by(
                type='lost', status='open',
                category=item.category, campus=item.campus
            ).all()
        
        matches = []
        for candidate in candidates:
            if item.id == candidate.id:
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
        
        db.session.commit()
        return notifications_created
