from .models import Book, Author, BookInstance, Genre
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.views.generic.edit import CreateView, UpdateView
from .models import Author, Book
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from .forms import LoanBookForm
import datetime

#imports for API
import requests
from django.conf import settings
from django.core.files.base import ContentFile

#image processing
from io import BytesIO
from PIL import Image 
import os



def index(request):
    """View function for home page of site."""
    num_books = Book.objects.all().count()
    num_instances = BookInstance.objects.all().count()

    # Available books (status = 'a')
    num_instances_available = BookInstance.objects.filter(status__exact='a').count()

    # The 'all()' is implied by default.
    num_authors = Author.objects.count()

    # Number of visits to this view, as counted in the session variable.
    num_visits = request.session.get('num_visits', 0)
    request.session['num_visits'] = num_visits + 1

    context = {
        'num_books': num_books,
        'num_instances': num_instances,
        'num_instances_available': num_instances_available,
        'num_authors': num_authors,
        'num_visits': num_visits,
    }
    # Render the HTML template index.html with the data in the context variable
    return render(request, 'catalog/index.html', context=context)



class BookListView(LoginRequiredMixin, generic.ListView):
    model = Book

class BookDetailView(LoginRequiredMixin, generic.DetailView):
    model = Book

class AuthorListView(LoginRequiredMixin, generic.ListView):
    model = Author
class AuthorDetailView(LoginRequiredMixin, generic.DetailView):
    model = Author


class AuthorDetailView(generic.DetailView):
    model = Author
    template_name = 'catalog/author_detail.html'
    context_object_name = 'author'


class LoanedBooksByUserListView(LoginRequiredMixin,generic.ListView):
    """Generic class-based view listing books on loan to current user."""
    model = BookInstance
    template_name = 'catalog/my_books.html'
    paginate_by = 10

    def get_queryset(self):
        return BookInstance.objects.filter \
            (borrower=self.request.user).filter(status__exact='o').order_by('due_back')

class AuthorCreate(CreateView):
    model = Author
    fields = ['first_name', 'last_name', 'date_of_birth', 'date_of_death', 'author_image']

    def form_valid(self, form):
        post = form.save(commit=False)
        file_name = f"{post.last_name}{post.first_name}.jpg"
        if not post.author_image == None:
            stock_path = os.path.join(settings.MEDIA_ROOT, 'images','StockAuthor.jpg')
            with open(stock_path, 'rb') as f:
                stock_content = f.read()
            post.author_image.save(file_name, ContentFile(stock_content), save=True)

        post.save()
        return HttpResponseRedirect(reverse('author_list'))

class AuthorUpdate(UpdateView):
    model = Author
    fields = ['first_name', 'last_name', 'date_of_birth', 'date_of_death', 'author_image']

    def form_valid(self, form):
        post = form.save(commit=False)
        file_name = f"{post.last_name}{post.first_name}.jpg"
        if not post.author_image == None:
            stock_path = os.path.join(settings.MEDIA_ROOT, 'images', 'StockAuthor.jpg')
            with open(stock_path, 'rb') as f:
                stock_content = f.read()
            post.author_image.save(file_name, ContentFile(stock_content), save=True)

        post.save()
        return HttpResponseRedirect(reverse('author_list'))

def author_delete(request, pk):
    author = get_object_or_404(Author, pk=pk)
    try:
        author.delete()
        messages.success(request, (author.first_name + ' ' + author.last_name +" has been deleted"))
    except:
        messages.success(request, (author.first_name + ' ' + author.last_name + ' cannot be deleted. Books exist for this author'))
    return redirect('author_list')

class AvailBooksListView(generic.ListView):
    model = BookInstance
    template_name = 'catalog/bookinstance_list_available.html'
    paginate_by = 10

    def get_queryset(self):
        return BookInstance.objects.filter(status__exact='a').order_by('book__title')


def loan_book_librarian(request, pk):
    """View function for renewing a specific BookInstance by librarian."""
    book_instance = get_object_or_404(BookInstance, pk=pk)
# If this is a POST request then process the Form data
    if request.method == 'POST':
# Create a form instance and populate it with data from the request (binding):
        form = LoanBookForm(request.POST, instance=book_instance)
# Check if the form is valid:
        if form.is_valid():
# process the data in form.cleaned_data as required (set due date and update status of book)
            book_instance = form.save()
            book_instance.due_back = datetime.date.today() + datetime.timedelta(weeks=4)
            book_instance.status = 'o'
            book_instance.save()
# redirect to a new URL:
            return HttpResponseRedirect(reverse('all_available'))
# If this is a GET (or any other method) create the default form
    else:
        form = LoanBookForm(instance=book_instance, initial={'book_title': book_instance.book.title})
        return render(request, 'catalog/loan_book_librarian.html', {'form':form})

class BookCreate(CreateView):
    model = Book
    fields = ['title', 'author', 'summary', 'isbn', 'genre', 'book_image']


    def form_valid(self, form):
        post = form.save(commit=False)
        post.save()
        # if the image not uploaded, get the image from an API
        if form.cleaned_data['book_image'] == None:
            bookImageFromAPI(post, form)

        for genre in form.cleaned_data['genre']:
            theGenre = get_object_or_404(Genre, name=genre)
            post.genre.add(theGenre)
            post.save()
        return HttpResponseRedirect(reverse('book_list'))

class BookUpdate(UpdateView):
    model = Book
    fields = ['title', 'author', 'summary', 'isbn', 'genre', 'book_image']

    def form_valid(self, form):
        post = form.save(commit=False)
        # if the image not uploaded, get the image from an API
        if form.cleaned_data['book_image'] == None:
            bookImageFromAPI(post, form)
        # delete previously stored genres for the book
        for genre in post.genre.all():
            post.genre.remove(genre)
        # for all genres selected on the form - add the genre many-to-many record
        for genre in form.cleaned_data['genre']:
            theGenre = get_object_or_404(Genre, name=genre)
            post.genre.add(theGenre)
        # save the database updates
        post.save()
        return HttpResponseRedirect(reverse('book_list'))

def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    book.delete()
    messages.success(request, (book.title + ' ' + " has been deleted"))
    return redirect('book_list')

#get books from API 
def author_get_books_api(request, pk):
    #Use the Google Books API to get a list of books for an author
    my_api_key = settings.GOOGLEBOOKS_API_KEY #get the API key from the settings file
    author = get_object_or_404(Author, pk=pk) #get author information from database
    #using the API key, request the books for the author using the first and last name
    authorRequest = requests.get('https://www.googleapis.com/books/v1/volumes?q=inauthor:%22'+ author.first_name+'+'+author.last_name+'%22&key=' + my_api_key)
    authorInfo_json = authorRequest.json()
    if (authorInfo_json['totalItems']==0):
        messages.success(request, (author.first_name + ' ' + author.last_name + ' has no books in Google Books'))
    else:
        for b in authorInfo_json['items']:
            try: #if any exceptions occur, the book will not be added
                title = b['volumeInfo']['title']
                if 'industryIdentifiers' in b['volumeInfo']:
                    isbn=b['volumeInfo']['industryIdentifiers'][0]['identifier']
                summary=b['volumeInfo']['description']
                imageURL = b['volumeInfo']['imageLinks']['smallThumbnail']

                book,created = Book.objects.get_or_create(title=title, author=author,
                        isbn=isbn, summary=summary)
                file_name = f"{isbn}.jpg"
                imageFound = False
                # If the book was created and an image URL exists,attempt to download and save it
                if created and imageURL:
                    response = requests.get(imageURL)
                    if response.status_code == 200:
                        if (validateImage(response.content)):
                            book.book_image.save(file_name, ContentFile(response.content), save=True)
                            imageFound = True
                if created and not imageFound: #use stock image if image not loaded
                    stock_path = os.path.join(settings.MEDIA_ROOT, 'images', 'StockBook.jpg')
                    with open(stock_path, 'rb') as f:
                        stock_content = f.read()
                    book.book_image.save(file_name, ContentFile(stock_content), save=True)

                # add Genres to database if they don't already exist
                for g in b['volumeInfo']['categories']:
                    newg=Genre.objects.get_or_create(name=g)

                #save the genres for this book
                book = get_object_or_404(Book, isbn=isbn)
                book.genre.add(*Genre.objects.filter(name__in=b['volumeInfo']['categories']))
                book.save()
            except: # if an error occurs, skip the book
                pass
    return redirect('author_detail', pk=author.pk)

# get book image from API 
def bookImageFromAPI(book, form):
    my_api_key = settings.GOOGLEBOOKS_API_KEY  # get the API key from the settings file
    # using the API key, request the book data using the ISBN number
    URL = ('https://www.googleapis.com/books/v1/volumes?q=' +
    form.cleaned_data['isbn'] + '%22&key=' + my_api_key)
    bookInfo_json = requests.get(URL).json()
    file_name = f"{form.cleaned_data['isbn']}.jpg"
    imageFound = False #assume no image in API
    # If the book was created and an image URL exists, download and save it
    if(bookInfo_json['totalItems']!=0):
        # Check if the API title matches the form title
        api_title = bookInfo_json['items'][0]['volumeInfo'].get('title', '').strip().lower()
        form_title = form.cleaned_data.get('title', '').strip().lower()
        if api_title != form_title:
            # Titles don't match, use stock image
            book.book_image.save(file_name, ContentFile(stock_content), save=True)
        else:
            imageURL = bookInfo_json['items'][0]['volumeInfo']['imageLinks']['smallThumbnail']
            if imageURL:
                response = requests.get(imageURL)
                if response.status_code == 200:
                    if(validateImage(response.content)):
                        book.book_image.save(file_name, ContentFile(response.content), save=True)
                        imageFound = True #image found in API
    if not imageFound:
        stock_path = os.path.join(settings.MEDIA_ROOT, 'images', 'StockBook.jpg')
        with open(stock_path, 'rb') as f:
            stock_content = f.read()
        book.book_image.save(file_name, ContentFile(stock_content), save=True)
    return form, book



# verify API image is not all black or all white
def validateImage(image):
    # Open the image and convert to RGB for consistent pixel checking
    img = Image.open(BytesIO(image)).convert('RGB')
    pixels = list(img.getdata())
    # Check if all pixels are black or white - bad image - use stock image
    if (all(p == (0, 0, 0) for p in pixels) or 
            all(p == (255, 255, 255) for p in pixels)):
        return False
    return True

class BookCopyCreate(CreateView):
    model = BookInstance
    fields = ['imprint'] # all the imprint type to be set for the book copy

    def get_initial(self):
        initial = super().get_initial()
        # Get the book object based on the pk in the URL
        book = get_object_or_404(Book, pk=self.kwargs.get('pk'))
        initial['book'] = book
        return initial

    def form_valid(self, form):
        # Ensure the book is assigned to the instance before saving
        form.instance.book = get_object_or_404(Book, pk=self.kwargs.get('pk'))
        form.instance.status = 'a'  #set the book to available when created
        copy = form.save(commit=False)
        copy.save()
        return redirect('book_detail', pk=self.kwargs.get('pk'))

