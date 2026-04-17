document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('live-search-input');
    const resultsDropdown = document.getElementById('live-search-results');
    const searchContainer = document.getElementById('nav-search-container');
    
    let debounceTimer;

    if (!searchInput || !resultsDropdown) return;

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        
        clearTimeout(debounceTimer);
        
        if (query.length < 2) {
            hideResults();
            return;
        }

        debounceTimer = setTimeout(() => {
            performSearch(query);
        }, 300);
    });

    // Cerrar al hacer click fuera
    document.addEventListener('click', (e) => {
        if (!searchContainer.contains(e.target)) {
            hideResults();
        }
    });

    // Cerrar con Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideResults();
            searchInput.blur();
        }
    });

    async function performSearch(query) {
        try {
            const response = await fetch(`/buscar/live/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            renderResults(data.productos);
        } catch (error) {
            console.error('Error en búsqueda live:', error);
        }
    }

    function renderResults(productos) {
        resultsDropdown.innerHTML = '';
        
        if (productos.length === 0) {
            resultsDropdown.innerHTML = '<div class="search-no-results">No se encontraron productos</div>';
        } else {
            productos.forEach(p => {
                const item = document.createElement('a');
                item.href = p.url;
                item.className = 'search-result-item';
                
                let imgHtml = '';
                if (p.imagen) {
                    imgHtml = `<img src="${p.imagen}" class="search-result-img" alt="${p.nombre}">`;
                } else {
                    imgHtml = `
                        <div class="search-result-placeholder">
                            <svg class="icon icon-sm" style="opacity: 0.3"><use xlink:href="#icon-package"></use></svg>
                        </div>
                    `;
                }

                item.innerHTML = `
                    ${imgHtml}
                    <div class="search-result-info">
                        <div class="search-result-name">${p.nombre}</div>
                        <div class="search-result-price">${p.precio}</div>
                    </div>
                `;
                
                resultsDropdown.appendChild(item);
            });
        }
        
        showResults();
    }

    function showResults() {
        resultsDropdown.classList.add('visible');
    }

    function hideResults() {
        resultsDropdown.classList.remove('visible');
    }
});
