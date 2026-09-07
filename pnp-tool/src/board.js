// board.js - Dynamically draws paths between nodes based on the page's data-connections attribute

document.addEventListener('DOMContentLoaded', () => {
    const pages = document.querySelectorAll('.page');
    
    pages.forEach(page => {
        const svg = page.querySelector('.map-lines');
        if (!svg) return;
        
        let connections = [];
        try {
            connections = JSON.parse(page.dataset.connections || '[]');
        } catch (e) {
            console.error('Failed to parse connections data', e);
        }
        
        connections.forEach(conn => {
            const id1 = conn[0];
            const id2 = conn[1];
            const type = conn[2] || 'standard';
            
            const el1 = document.getElementById(id1);
            const el2 = document.getElementById(id2);
            
            if (el1 && el2) {
                // Get positions relative to the page
                const rect1 = el1.getBoundingClientRect();
                const rect2 = el2.getBoundingClientRect();
                const pageRect = page.getBoundingClientRect();
                
                const x1 = rect1.left + rect1.width / 2 - pageRect.left;
                const y1 = rect1.top + rect1.height / 2 - pageRect.top;
                const x2 = rect2.left + rect2.width / 2 - pageRect.left;
                const y2 = rect2.top + rect2.height / 2 - pageRect.top;
                
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', x1);
                line.setAttribute('y1', y1);
                line.setAttribute('x2', x2);
                line.setAttribute('y2', y2);
                
                // Style based on type
                if (type === 'flight') {
                    line.setAttribute('stroke', '#1a3f63');
                    line.setAttribute('stroke-width', '4');
                    line.setAttribute('stroke-dasharray', '12 8');
                } else {
                    line.setAttribute('stroke', '#8b5a2b');
                    line.setAttribute('stroke-width', '3');
                    line.setAttribute('stroke-dasharray', '8 6');
                }
                
                svg.appendChild(line);
            }
        });
    });
});
