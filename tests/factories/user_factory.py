"""factory_boy фабрики для мобильных тестовых данных."""

from __future__ import annotations

import uuid

import factory
from faker import Faker

fake = Faker()


class MobileUserFactory(factory.DictFactory):
    username = factory.LazyFunction(lambda: f"mob_{uuid.uuid4().hex[:8]}")
    password = "10203040"
    email = factory.LazyFunction(lambda: f"mob_{uuid.uuid4().hex[:8]}@test.com")
    first_name = factory.LazyFunction(lambda: fake.first_name())
    last_name = factory.LazyFunction(lambda: fake.last_name())


class ShippingAddressFactory(factory.DictFactory):
    full_name = factory.LazyFunction(lambda: fake.name())
    address = factory.LazyFunction(lambda: fake.street_address())
    city = factory.LazyFunction(lambda: fake.city())
    zip_code = factory.LazyFunction(lambda: fake.zipcode())
    country = "United States"


class ProductFactory(factory.DictFactory):
    name = factory.LazyFunction(lambda: fake.word().capitalize() + " " + fake.word())
    price = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=1, max_value=500, right_digits=2), 2)
    )
    category = factory.Iterator(["beauty", "electronics", "clothing", "sports"])
    stock = factory.LazyFunction(lambda: fake.random_int(min=0, max=100))
