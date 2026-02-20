"""
Location Management System - CRUD operations for Country and City models
"""
from db_country import Country
from db_city import City
from datetime import datetime
from typing import Optional, List

# ==================== COUNTRY OPERATIONS ====================

def create_country(name: str) -> Optional[Country]:
    """
    1. Create new Country
    
    Args:
        name: Name of the country
    
    Returns:
        Country object if successful, None otherwise
    """
    try:
        # Check if country already exists
        existing = Country.objects(name=name).first()
        if existing:
            print(f"❌ Country '{name}' already exists with ID: {existing.id}")
            return None
        
        country = Country(
            name=name,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        country.save()
        print(f"✅ Created country: {country.name} (ID: {country.id})")
        return country
    except Exception as e:
        print(f"❌ Error creating country: {e}")
        return None


def update_country(country_id: Optional[int] = None, country_name: Optional[str] = None, 
                   new_name: str = None) -> Optional[Country]:
    """
    2. Update a country
    
    Args:
        country_id: ID of the country to update
        country_name: Name of the country to update (alternative to ID)
        new_name: New name for the country
    
    Returns:
        Updated Country object if successful, None otherwise
    """
    try:
        # Find country by ID or name
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return None
        
        if not country:
            print(f"❌ Country not found")
            return None
        
        old_name = country.name
        country.name = new_name
        country.updated_at = datetime.utcnow()
        country.save()
        print(f"✅ Updated country: '{old_name}' → '{country.name}'")
        return country
    except Exception as e:
        print(f"❌ Error updating country: {e}")
        return None


def delete_country(country_id: Optional[int] = None, country_name: Optional[str] = None) -> bool:
    """
    3. Delete a Country (will cascade delete all cities in that country)
    
    Args:
        country_id: ID of the country to delete
        country_name: Name of the country to delete (alternative to ID)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Find country by ID or name
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return False
        
        if not country:
            print(f"❌ Country not found")
            return False
        
        # Count cities that will be deleted
        cities_count = City.objects(country=country).count()
        country_name = country.name
        
        # Delete country (cascade will delete all cities)
        country.delete()
        print(f"✅ Deleted country: '{country_name}' (cascade deleted {cities_count} cities)")
        return True
    except Exception as e:
        print(f"❌ Error deleting country: {e}")
        return False


def get_countries() -> List[Country]:
    """
    4. Get list of all countries
    
    Returns:
        List of all Country objects
    """
    try:
        countries = Country.objects().order_by('name')
        print(f"📋 Total countries: {countries.count()}")
        for country in countries:
            city_count = City.objects(country=country).count()
            print(f"  - {country.name} (ID: {country.id}) - {city_count} cities")
        return list(countries)
    except Exception as e:
        print(f"❌ Error getting countries: {e}")
        return []


def search_country(name: Optional[str] = None, country_id: Optional[int] = None) -> Optional[Country]:
    """
    5. Search country based on name or id
    
    Args:
        name: Country name to search (supports partial match)
        country_id: Country ID to search
    
    Returns:
        Country object if found, None otherwise
    """
    try:
        if country_id:
            country = Country.objects(id=country_id).first()
            if country:
                city_count = City.objects(country=country).count()
                print(f"🔍 Found: {country.name} (ID: {country.id}) - {city_count} cities")
                return country
            else:
                print(f"❌ No country found with ID: {country_id}")
                return None
        
        elif name:
            # Search by exact name or partial match
            countries = Country.objects(name__icontains=name)
            if countries.count() == 0:
                print(f"❌ No countries found matching '{name}'")
                return None
            
            print(f"🔍 Found {countries.count()} matching countries:")
            for country in countries:
                city_count = City.objects(country=country).count()
                print(f"  - {country.name} (ID: {country.id}) - {city_count} cities")
            
            return countries.first() if countries.count() == 1 else list(countries)
        
        else:
            print("❌ Please provide either name or country_id")
            return None
    except Exception as e:
        print(f"❌ Error searching country: {e}")
        return None


# ==================== CITY OPERATIONS ====================

def create_city(name: str, country_id: Optional[int] = None, 
                country_name: Optional[str] = None) -> Optional[City]:
    """
    6. Create a new city
    
    Args:
        name: Name of the city
        country_id: ID of the country (either country_id or country_name required)
        country_name: Name of the country (alternative to country_id)
    
    Returns:
        City object if successful, None otherwise
    """
    try:
        # Find country
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return None
        
        if not country:
            print(f"❌ Country not found")
            return None
        
        # Check if city already exists in that country
        existing = City.objects(name=name, country=country).first()
        if existing:
            print(f"❌ City '{name}' already exists in {country.name} with ID: {existing.id}")
            return None
        
        city = City(
            name=name,
            country=country,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        city.save()
        print(f"✅ Created city: {city.name} in {city.country.name} (ID: {city.id})")
        return city
    except Exception as e:
        print(f"❌ Error creating city: {e}")
        return None


def update_city(city_id: Optional[int] = None, city_name: Optional[str] = None,
                new_name: Optional[str] = None, new_country_id: Optional[int] = None) -> Optional[City]:
    """
    7. Update a city
    
    Args:
        city_id: ID of the city to update
        city_name: Name of the city to update (alternative to ID)
        new_name: New name for the city
        new_country_id: New country ID (optional, to move city to different country)
    
    Returns:
        Updated City object if successful, None otherwise
    """
    try:
        # Find city by ID or name
        if city_id:
            city = City.objects(id=city_id).first()
        elif city_name:
            city = City.objects(name=city_name).first()
        else:
            print("❌ Please provide either city_id or city_name")
            return None
        
        if not city:
            print(f"❌ City not found")
            return None
        
        old_info = f"{city.name} ({city.country.name})"
        
        # Update name if provided
        if new_name:
            city.name = new_name
        
        # Update country if provided
        if new_country_id:
            new_country = Country.objects(id=new_country_id).first()
            if not new_country:
                print(f"❌ Country with ID {new_country_id} not found")
                return None
            city.country = new_country
        
        city.updated_at = datetime.utcnow()
        city.save()
        
        new_info = f"{city.name} ({city.country.name})"
        print(f"✅ Updated city: '{old_info}' → '{new_info}'")
        return city
    except Exception as e:
        print(f"❌ Error updating city: {e}")
        return None


def delete_city(city_id: Optional[int] = None, city_name: Optional[str] = None) -> bool:
    """
    8. Delete a city
    
    Args:
        city_id: ID of the city to delete
        city_name: Name of the city to delete (alternative to ID)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Find city by ID or name
        if city_id:
            city = City.objects(id=city_id).first()
        elif city_name:
            city = City.objects(name=city_name).first()
        else:
            print("❌ Please provide either city_id or city_name")
            return False
        
        if not city:
            print(f"❌ City not found")
            return False
        
        city_info = f"{city.name} ({city.country.name})"
        city.delete()
        print(f"✅ Deleted city: {city_info}")
        return True
    except Exception as e:
        print(f"❌ Error deleting city: {e}")
        return False


def get_cities() -> List[City]:
    """
    9. Get list of all cities
    
    Returns:
        List of all City objects
    """
    try:
        cities = City.objects().order_by('name')
        print(f"📋 Total cities: {cities.count()}")
        for city in cities:
            print(f"  - {city.name} in {city.country.name} (ID: {city.id})")
        return list(cities)
    except Exception as e:
        print(f"❌ Error getting cities: {e}")
        return []


def search_city(name: Optional[str] = None, city_id: Optional[int] = None) -> Optional[City]:
    """
    10. Search city based on city name or id
    
    Args:
        name: City name to search (supports partial match)
        city_id: City ID to search
    
    Returns:
        City object if found, None otherwise
    """
    try:
        if city_id:
            city = City.objects(id=city_id).first()
            if city:
                print(f"🔍 Found: {city.name} in {city.country.name} (ID: {city.id})")
                return city
            else:
                print(f"❌ No city found with ID: {city_id}")
                return None
        
        elif name:
            # Search by exact name or partial match
            cities = City.objects(name__icontains=name)
            if cities.count() == 0:
                print(f"❌ No cities found matching '{name}'")
                return None
            
            print(f"🔍 Found {cities.count()} matching cities:")
            for city in cities:
                print(f"  - {city.name} in {city.country.name} (ID: {city.id})")
            
            return cities.first() if cities.count() == 1 else list(cities)
        
        else:
            print("❌ Please provide either name or city_id")
            return None
    except Exception as e:
        print(f"❌ Error searching city: {e}")
        return None


def get_cities_by_country(country_id: Optional[int] = None, 
                          country_name: Optional[str] = None) -> List[City]:
    """
    11. Get list of cities based on country
    
    Args:
        country_id: ID of the country
        country_name: Name of the country (alternative to ID)
    
    Returns:
        List of City objects in that country
    """
    try:
        # Find country
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return []
        
        if not country:
            print(f"❌ Country not found")
            return []
        
        cities = City.objects(country=country).order_by('name')
        print(f"📋 Cities in {country.name}: {cities.count()}")
        for city in cities:
            print(f"  - {city.name} (ID: {city.id})")
        return list(cities)
    except Exception as e:
        print(f"❌ Error getting cities by country: {e}")
        return []


# ==================== DEMO/TEST FUNCTIONS ====================

def demo():
    """
    Demonstration of all functions
    """
    print("=" * 60)
    print("LOCATION MANAGEMENT SYSTEM - DEMO")
    print("=" * 60)
    
    # 1. Create countries
    print("\n1. Creating countries...")
    france = create_country("France")
    spain = create_country("Spain")
    italy = create_country("Italy")
    
    # 2. Create cities
    print("\n6. Creating cities...")
    create_city("Paris", country_name="France")
    create_city("Lyon", country_name="France")
    create_city("Marseille", country_name="France")
    create_city("Madrid", country_name="Spain")
    create_city("Barcelona", country_name="Spain")
    create_city("Rome", country_name="Italy")
    
    # 4. List all countries
    print("\n4. Listing all countries...")
    get_countries()
    
    # 9. List all cities
    print("\n9. Listing all cities...")
    get_cities()
    
    # 11. Get cities by country
    print("\n11. Getting cities by country (France)...")
    get_cities_by_country(country_name="France")
    
    # 5. Search country
    print("\n5. Searching for country (by name 'Fra')...")
    search_country(name="Fra")
    
    # 10. Search city
    print("\n10. Searching for city (by name 'paris')...")
    search_city(name="paris")
    
    # 2. Update country
    print("\n2. Updating country (Spain → España)...")
    update_country(country_name="Spain", new_name="España")
    
    # 7. Update city
    print("\n7. Updating city (Madrid → Madrid Capital)...")
    update_city(city_name="Madrid", new_name="Madrid Capital")
    
    # 8. Delete a city
    print("\n8. Deleting city (Lyon)...")
    delete_city(city_name="Lyon")
    
    # Show final state
    print("\nFinal state after updates and deletions:")
    get_countries()
    
    # 3. Delete country with cascade
    print("\n3. Deleting country (France) - will cascade delete all cities...")
    delete_country(country_name="France")
    
    print("\nFinal cities after country deletion:")
    get_cities()


# if __name__ == "__main__":
#     create_country("Senegal")
#     create_country("France")

#     create_city("Dakar", country_name="Senegal")
#     create_city("Paris", country_name="France")
#     create_city("Thiès", country_name="Senegal")
#     create_city("Lyon", country_name="France")