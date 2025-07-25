from django.db import models
from django.utils.text import slugify

class List(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    municipality_scores = models.JSONField(default=dict)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while List.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f"List(name={self.name}, slug={self.slug})"

class Label(models.Model):
    list = models.ForeignKey(List, related_name="labels", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("list", "name")

    def __str__(self):
        return self.name

class ListItem(models.Model):
    list = models.ForeignKey(List, related_name='items', on_delete=models.CASCADE)
    company = models.ForeignKey('companies.Company', related_name='list_items', on_delete=models.CASCADE)
    label = models.ForeignKey(Label, null=True, blank=True, on_delete=models.SET_NULL, related_name="list_items")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('list', 'company')

    def __str__(self):
        return f"{self.company.name} in {self.list.name} [self.label.name if self.label else 'No Label']"
    
    def __repr__(self):
        return f"ListItem(list={self.list.name}, company={self.company.name})"
    
class Municipality(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=5, unique=True)

    def __str__(self):
        return f"{self.name} ({self.nis_code})"