document.addEventListener("DOMContentLoaded", () => {
    // Handle Auto-hide Flash Messages (Pop-up Feature)
    const toasts = document.querySelectorAll('.brutalist-toast');
    
    toasts.forEach(toast => {
        // Automatically remove after 3.5 seconds
        setTimeout(() => {
            toast.style.transition = 'all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)';
            toast.style.transform = 'translate(100px, -100px)';
            toast.style.opacity = '0';
            
            setTimeout(() => {
                toast.remove();
            }, 500);
        }, 3500);
        
        // Manual Close on Click
        toast.addEventListener('click', () => {
            toast.remove();
        });
    });
});
