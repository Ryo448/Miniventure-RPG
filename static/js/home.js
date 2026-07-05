const Home = {
    init() {
        this.setupButtonAnimations();
    },

    setupButtonAnimations() {
        const buttons = document.querySelectorAll('.btn-animate');
        buttons.forEach((btn) => {
            btn.addEventListener('mouseenter', () => {
                btn.style.transform = 'translateY(-2px)';
                btn.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
            });

            btn.addEventListener('mouseleave', () => {
                btn.style.transform = 'translateY(0)';
                btn.style.boxShadow = '';
            });

            btn.addEventListener('mousedown', () => {
                btn.style.transform = 'translateY(1px)';
            });

            btn.addEventListener('mouseup', () => {
                btn.style.transform = 'translateY(-2px)';
            });
        });
    },
};

document.addEventListener('DOMContentLoaded', () => {
    Home.init();
});
