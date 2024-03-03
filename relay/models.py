from django.db import models


class Chain(models.TextChoices):
    COSTON = "coston"
    SEPOLIA = "sepolia"


class Block(models.Model):
    chain = models.CharField(max_length=7, choices=Chain.choices, unique=True)
    number = models.PositiveIntegerField()
    timestamp = models.PositiveIntegerField()

    def __str__(self):
        return f"Chain: {self.chain} Number: {self.number} Timestamp: {self.timestamp}"
