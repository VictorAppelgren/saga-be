document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            if (this.classList.contains('bg-white')) {
                this.classList.remove('bg-white', 'text-black');
                this.classList.add('bg-black', 'text-white');
            } else {
                document.querySelectorAll('.category-btn').forEach(b => {
                    b.classList.remove('bg-white', 'text-black');
                    b.classList.add('bg-black', 'text-white');
                });
                this.classList.remove('bg-black', 'text-white');
                this.classList.add('bg-white', 'text-black');
            }
        });
    });
});
