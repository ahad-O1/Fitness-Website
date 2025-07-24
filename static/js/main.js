/*=============== SHOW MENU ===============*/
navToggle = document.getElementById('nav-toggle'),
navClose = document.getElementById('nav-close')

/* Menu show */
if(navToggle){
    navToggle.addEventListener('click', () =>{
        navMenu.classList.add('show-menu')  // FIXED: Changed 'remove' to 'add' to show the menu
    })
}

/*=============== REMOVE MENU MOBILE ===============*/
if(navClose){
    navClose.addEventListener('click', () =>{
        navMenu.classList.remove('show-menu')
    })
}

const navLink = document.querySelectorAll('.nav__link')

const linkAction = () =>{
    const navMenu = document.getElementById('nav-menu')
    // When we click on each nav__link, we remove the show-menu class
    navMenu.classList.remove('show-menu')
}
navLink.forEach(n => n.addEventListener('click', linkAction))

/*=============== CHANGE BACKGROUND HEADER ===============*/
const scrollHeader = () =>{
    const header = document.getElementById('header')
    // When the scroll is greater than 50 viewport height, add the scroll-header class to the header tag
    this.scrollY >= 50 ? header.classList.add('bg-header') 
                       : header.classList.remove('bg-header')
}
window.addEventListener('scroll', scrollHeader)


/*=============== SCROLL SECTIONS ACTIVE LINK ===============*/
const sections = document.querySelectorAll('section[id]')
    
const scrollActive = () =>{
    const scrollY = window.pageYOffset

    sections.forEach(current =>{
        const sectionHeight = current.offsetHeight,
              sectionTop = current.offsetTop - 58,
              sectionId = current.getAttribute('id'),
              sectionsClass = document.querySelector('.nav__menu a[href*=' + sectionId + ']')

        if(scrollY > sectionTop && scrollY <= sectionTop + sectionHeight){
            sectionsClass.classList.add('active-link')
        }else{
            sectionsClass.classList.remove('active-link')
        }                                                    
    })
}
window.addEventListener('scroll', scrollActive)


/*=============== SHOW SCROLL UP ===============*/ 
const scrollUp = () =>{
    const scrollUp = document.getElementById('scroll-up')
    // When the scroll is higher than 350 viewport height, add the show-scroll class to the a tag with the scrollup class
    this.scrollY >= 350 ? scrollUp.classList.add('show-scroll')
                        : scrollUp.classList.remove('show-scroll')
}
window.addEventListener('scroll', scrollUp)

/*=============== SCROLL REVEAL ANIMATION ===============*/
// Initialize ScrollReveal with default configuration
const sr = ScrollReveal({
    origin: 'top',         // Elements will animate from the top
    distance: '60px',      // Elements will move 60px during animation
    duration: 2500,        // Animation duration in milliseconds
    delay: 400,            // Delay before animation starts
    // reset: true         // Uncomment to make animations repeat on scroll up
})

// Apply animations to different sections
// Home section animations
sr.reveal(`.home__data, .home__title, .home__subtitle, .home__description, .home__button`, {
    origin: 'top',
    interval: 100          // Elements will animate with 100ms delay between each
})
sr.reveal(`.home__img`, {
    delay: 700,
    origin: 'bottom'       // This element will animate from the bottom
})

// About section animations
sr.reveal(`.about__data`, {origin: 'left'})
sr.reveal(`.about__img`, {origin: 'right'})

// Services/Features section animations
sr.reveal(`.services__card, .features__card`, {interval: 100})

// Team/Testimonial section animations
sr.reveal(`.team__card, .testimonial__card`, {interval: 200})

// Logo/Partner animations
sr.reveal(`.logos__img`, {interval: 100})

// Program/Product section animations
sr.reveal(`.program__card, .products__card`, {interval: 100})

// Blog/News section animations
sr.reveal(`.blog__card`, {
    interval: 100,
    origin: 'bottom'
})

// Pricing section
sr.reveal(`.pricing__card`, {interval: 100})

// Contact section
sr.reveal(`.contact__information`, {origin: 'left'})
sr.reveal(`.contact__form`, {origin: 'right'})

// Special section animations
sr.reveal(`.choose__img, .calculate__img`, {origin: 'left'})
sr.reveal(`.choose__content, .calculate__content`, {origin: 'right'})
sr.reveal(`.steps__card, .plan__card`, {interval: 100})

// Footer animations
sr.reveal(`.footer__container, .footer__group, .footer__content`, {
    interval: 100,
    origin: 'top'
})

/*=============== CALCULATE JS ===============*/
const calculateForm = document.getElementById('calculate-form'),
      calculateCm = document.getElementById('calculate-cm'),
      calculateKg = document.getElementById('calculate-kg'),
      calculateMessage = document.getElementById('calculate-message')

const calculateBmi = (e) => {
    e.preventDefault()
    
    // Check if the fields have a value
    if(calculateCm.value === '' || calculateKg.value === ''){
        // Add and remove color
        calculateMessage.classList.remove('color-green')
        calculateMessage.classList.add('color-red')
        
        // Show message
        calculateMessage.textContent = 'Fill in the Height and Weight 👨‍💻'
        
        // Remove message after 3 seconds
        setTimeout(() => {
            calculateMessage.textContent = ''
        }, 3000)
    } else {
        // BMI Formula
        const cm = calculateCm.value / 100
        const kg = calculateKg.value
        const bmi = Math.round(kg / (cm * cm))
        
        // Show health status
        if(bmi < 18.5){
            // Add color and display message
            calculateMessage.classList.add('color-green')
            calculateMessage.textContent = `Your BMI is ${bmi} and you are skinny 😔`
        } else if(bmi < 25){
            calculateMessage.classList.add('color-green')
            calculateMessage.textContent = `Your BMI is ${bmi} and you are healthy 🥳`
        } else {
            calculateMessage.classList.add('color-green')
            calculateMessage.textContent = `Your BMI is ${bmi} and you are overweight 😔`
        }
        
        // Clear input fields
        calculateCm.value = ''
        calculateKg.value = ''
        
        // Remove message after 4 seconds
        setTimeout(() => {
            calculateMessage.textContent = ''
        }, 4000)
    }
}

calculateForm.addEventListener('submit', calculateBmi)

/*=============== EMAIL JS ===============*/
const contactForm = document.getElementById('contact-form');
const contactMessage = document.getElementById('contact-message');
const contactUser = document.getElementById('contact-user');

const sendEmail = (e) => {
    e.preventDefault();
    
    // Check if the email field has a value and is valid
    const email = contactUser.value.trim();
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    
    if (!email) {
        displayMessage('You must enter your email 👆', 'red');
        return;
    }
    
    if (!emailPattern.test(email)) {
        displayMessage('Please enter a valid email address', 'red');
        return;
    }
    
    // Show loading message
    displayMessage('Sending...', '');
    
    // Create template parameters object - IMPORTANT!
    // This ensures your email template gets the right values
    const templateParams = {
        user_email: email,
        to_email: email, // Send verification to the user's email
        message: 'Thank you for registering!'
    };
    
    // Try sending with direct parameters instead of form
    emailjs.send('service_izjh6ha', 'template_d19ouxh', templateParams)
        .then((response) => {
            console.log('SUCCESS!', response.status, response.text);
            displayMessage('You registered successfully 💪', 'green');
            contactUser.value = ''; // Clear input field
        })
        .catch((error) => {
            console.error('FAILED...', error);
            displayMessage(`Registration failed: ${error.text || 'Service error'}`, 'red');
        });
};

// Helper function to display messages
function displayMessage(text, color) {
    contactMessage.textContent = text;
    contactMessage.classList.remove('color-green', 'color-red');
    
    if (color === 'green') {
        contactMessage.classList.add('color-green');
    } else if (color === 'red') {
        contactMessage.classList.add('color-red');
    }
    
    if (text !== 'Sending...') {
        // Clear message after delay (except for "Sending...")
        setTimeout(() => {
            contactMessage.textContent = '';
        }, 5000);
    }
}

// Make sure the form exists before adding event listener
if (contactForm) {
    contactForm.addEventListener('submit', sendEmail);
} else {
    console.error('Contact form element not found!');
}

// sign up functionality
let isSignup = true;

function openAuthModal() {
    document.getElementById("authModal").style.display = "block";
    toggleForm("signup");
}

function closeAuthModal() {
    document.getElementById("authModal").style.display = "none";
}

function toggleForm(type) {
    const formTitle = document.getElementById("formTitle");
    const form = document.getElementById("authForm");
    isSignup = type === "signup";
    
    formTitle.textContent = isSignup ? "Sign Up" : "Login";
    
    document.getElementById("name").style.display = isSignup ? "block" : "none";
    document.getElementById("phone").style.display = isSignup ? "block" : "none";
    document.getElementById("dob").style.display = isSignup ? "block" : "none";
    form.querySelector('input[type="submit"]').value = isSignup ? "Sign Up" : "Login";
    
    form.querySelector("p").innerHTML = isSignup
      ? 'Already have an account? <a href="#" onclick="toggleForm(\'login\')" style="color:limegreen;">Login</a>'
      : 'Don\'t have an account? <a href="#" onclick="toggleForm(\'signup\')" style="color:limegreen;">Sign Up</a>';
}

function handleFormSubmit(event) {
    event.preventDefault();
    const email = document.getElementById("email").value;
    const pwd = document.getElementById("password").value;
    
    if (isSignup) {
        alert("Signed up successfully. Now login.");
        toggleForm("login");
    } else {
        alert("Logged in successfully!");
        closeAuthModal();
    }
    return false;
}

const programDetails = {
    "Flex Muscle": "Flex muscle training creates tension in muscles that promotes flexibility, strength, and injury prevention. It involves controlled movements to stretch and contract muscles through their full range of motion.",
    "Cardio Exercise": "Cardio exercise increases your heart rate and breathing. It improves cardiovascular endurance, burns fat, and helps with overall fitness. Common examples include running, cycling, and jumping rope.",
    "Basic Yoga": "Basic yoga focuses on breathing techniques and fundamental poses. It helps improve flexibility, reduce stress, and strengthen core muscles. It's ideal for beginners seeking calmness and balance.",
    "Weight Lifting": "Weight lifting builds muscle mass and strength through resistance training. It involves lifting heavy weights with proper form and progressive overload to increase muscle growth and endurance."
};

function showProgramDetail(programName) {
    document.getElementById('programModalTitle').innerText = programName;
    document.getElementById('programModalContent').innerText = programDetails[programName];
    document.getElementById('programModal').style.display = 'block';
}

function closeProgramModal() {
    document.getElementById('programModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('programModal');
    if (event.target === modal) {
        closeProgramModal();
    }
};

/*=============== PURCHASE HANDLING FOR DJANGO ===============*/
// Function to handle purchase button clicks with Django authentication
function handlePurchase(packageName, price) {
    // Check if user is authenticated (this will be set in the template)
    if (typeof isUserAuthenticated !== 'undefined' && isUserAuthenticated) {
        // User is logged in - show confirmation and proceed with purchase
        if (confirm(`Are you sure you want to purchase ${packageName} for ${price}?`)) {
            // Create a form and submit it
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = purchaseUrl;  // This will be set in the template
            
            // Add CSRF token
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = csrfToken;  // This will be set in the template
            form.appendChild(csrfInput);
            
            // Add package name
            const packageInput = document.createElement('input');
            packageInput.type = 'hidden';
            packageInput.name = 'package_name';
            packageInput.value = packageName;
            form.appendChild(packageInput);
            
            // Add package price
            const priceInput = document.createElement('input');
            priceInput.type = 'hidden';
            priceInput.name = 'package_price';
            priceInput.value = price;
            form.appendChild(priceInput);
            
            // Submit the form
            document.body.appendChild(form);
            form.submit();
        }
    } else {
        // User is not logged in - show confirmation dialog
        if (confirm('You need to login first to purchase a package. Click OK to go to login page.')) {
            // Redirect to login page using the correct URL
            window.location.href = loginUrl;  // This will be set in the template
        }
    }
}