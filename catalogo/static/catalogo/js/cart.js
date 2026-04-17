const Cart = {
    csrfToken: null,

    init() {
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || document.querySelector('meta[name="csrf-token"]')?.content;
        this.updateBadge();
        this.bindEvents();
    },

    bindEvents() {
        document.addEventListener('click', (e) => {
            const addBtn = e.target.closest('.js-add-cart');
            if (addBtn) {
                e.preventDefault();
                this.addItem(addBtn);
            }

            const removeBtn = e.target.closest('.js-remove-item');
            if (removeBtn) {
                e.preventDefault();
                this.removeItem(removeBtn);
            }

            const clearBtn = e.target.closest('.js-clear-cart');
            if (clearBtn) {
                e.preventDefault();
                this.clearCart();
            }

            const qtyMinus = e.target.closest('.js-qty-minus');
            if (qtyMinus) {
                e.preventDefault();
                this.changeQty(qtyMinus, -1);
            }

            const qtyPlus = e.target.closest('.js-qty-plus');
            if (qtyPlus) {
                e.preventDefault();
                this.changeQty(qtyPlus, 1);
            }
        });
    },

    async addItem(btn) {
        const productId = btn.dataset.productId;
        const qtyInput = document.querySelector(`#qty-${productId}`);
        const cantidad = qtyInput ? parseInt(qtyInput.value) || 1 : 1;

        btn.disabled = true;
        const originalText = btn.innerHTML;
        btn.innerHTML = '⏳ Agregando...';

        try {
            const response = await fetch('/carrito/agregar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken,
                },
                body: `producto_id=${productId}&cantidad=${cantidad}`,
            });

            const data = await response.json();

            if (data.ok) {
                this.updateBadgeCount(data.cart_count);
                this.showToast(`✅ ${data.nombre} agregado al carrito`);
                btn.innerHTML = '✓ Agregado';
                setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 1500);
            } else {
                this.showToast(`❌ ${data.error}`, 'error');
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        } catch (err) {
            this.showToast('❌ Error de conexión', 'error');
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    },

    async removeItem(btn) {
        const productId = btn.dataset.productId;

        try {
            const response = await fetch('/carrito/eliminar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken,
                },
                body: `producto_id=${productId}`,
            });

            const data = await response.json();
            if (data.ok) {
                this.updateBadgeCount(data.cart_count);
                const row = btn.closest('.cart-item');
                if (row) {
                    row.style.transition = 'all 0.3s ease';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(30px)';
                    setTimeout(() => {
                        row.remove();
                        this.updateCartPage(data);
                    }, 300);
                }
            }
        } catch (err) {
            this.showToast('❌ Error de conexión', 'error');
        }
    },

    async changeQty(btn, delta) {
        const productId = btn.dataset.productId;
        const input = document.querySelector(`#cart-qty-${productId}`);
        if (!input) return;

        let newQty = parseInt(input.value) + delta;
        if (newQty < 1) newQty = 1;
        input.value = newQty;

        try {
            const response = await fetch('/carrito/actualizar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken,
                },
                body: `producto_id=${productId}&cantidad=${newQty}`,
            });

            const data = await response.json();
            if (data.ok) {
                this.updateBadgeCount(data.cart_count);
                this.updateCartPage(data);
                const subtotalEl = document.querySelector(`#subtotal-${productId}`);
                if (subtotalEl) {
                    subtotalEl.textContent = data.item_subtotal;
                }
            }
        } catch (err) {
            this.showToast('❌ Error de conexión', 'error');
        }
    },

    async clearCart() {
        if (!confirm('¿Vaciar todo el carrito?')) return;

        try {
            const response = await fetch('/carrito/vaciar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken,
                },
                body: '',
            });

            const data = await response.json();
            if (data.ok) {
                this.updateBadgeCount(0);
                location.reload();
            }
        } catch (err) {
            this.showToast('❌ Error de conexión', 'error');
        }
    },

    updateBadge() {
        fetch('/carrito/count/')
            .then(r => r.json())
            .then(data => this.updateBadgeCount(data.count))
            .catch(() => {});
    },

    updateBadgeCount(count) {
        const badges = document.querySelectorAll('.cart-badge');
        badges.forEach(badge => {
            badge.textContent = count;
            if (count > 0) {
                badge.classList.add('visible');
                badge.style.animation = 'pulse 0.3s ease';
                setTimeout(() => { badge.style.animation = ''; }, 300);
            } else {
                badge.classList.remove('visible');
            }
        });
    },

    updateCartPage(data) {
        const totalEl = document.querySelector('#cart-total');
        const subtotalEl = document.querySelector('#cart-subtotal');
        const countEl = document.querySelector('#cart-items-count');
        if (totalEl && data.cart_total) totalEl.textContent = data.cart_total;
        if (subtotalEl && data.cart_total) subtotalEl.textContent = data.cart_total;
        if (countEl) countEl.textContent = data.cart_count;

        if (data.cart_count === 0) {
            location.reload();
        }
    },

    showToast(message, type = 'success') {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => toast.remove(), 3000);
    }
};

document.addEventListener('DOMContentLoaded', () => Cart.init());
