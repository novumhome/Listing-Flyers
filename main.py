import psycopg2
from flask import Flask, redirect, render_template, request, url_for
import re  # Add this line to import the 're' module
app = Flask(__name__)

# Database connection
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="UM8IZK5nvSQf",
    host="ep-shrill-bonus-a5jb4pas.us-east-2.aws.neon.tech",
    port="5432"
)

# Custom filter to format currency
@app.template_filter('format_currency')
def format_currency(value):
    return "${:,.0f}".format(value)

# Mapping of full state names to abbreviations
state_mapping = {
    "texas": "TX",
    "oklahoma": "OK",
    # Add other states as needed
}

def extract_state_from_address(address):
    # Regular expression to find state abbreviation or full state name
    state_pattern = re.compile(r'\b(TX|OK|Texas|Oklahoma)\b', re.IGNORECASE)
    match = state_pattern.search(address)

    if match:
        state = match.group(0).strip().lower()
        # Convert full state name to abbreviation if necessary
        return state_mapping.get(state, state.upper())
    else:
        return None  # Handle case where no state is found

@app.route('/')
def form():
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    sales_price = request.form['sales_price']
    address = request.form['subject_property_address']
    property_tax = request.form['property_tax']
    seller_incentives = request.form['seller_incentives']

    # Extract the state from the address
    state = extract_state_from_address(address)

    # Collect the selected loan programs from the form as a list
    loan_programs = request.form.getlist('loan_program')

    # Convert the list to a PostgreSQL array format
    loan_programs_array = '{' + ','.join(loan_programs) + '}'

    cursor = conn.cursor()

    insert_query = """
    INSERT INTO new_record (
        sales_price,
        subject_property_address,
        property_tax_amount,
        seller_incentives,
        loan_programs,
        state
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING record_id
"""

    try:
        cursor.execute(insert_query, (sales_price, address, property_tax, seller_incentives, loan_programs_array, state))
        record_id = cursor.fetchone()[0]
        conn.commit()
        print("Record inserted successfully.")

        # Fetch all loan_scenario_results for the given record_id
        select_results_query = """
        SELECT loan_program_code, total_loan_amount, amount_needed_to_purchase, total_payment,
               interest_rate, apr, discount_points_percent
        FROM loan_scenario_results
        WHERE record_id = %s
        """
        cursor.execute(select_results_query, (record_id,))
        raw_results = cursor.fetchall()

        # Structure the data into a dictionary
        results = {}
        for row in raw_results:
            loan_program_code = row[0]
            results[loan_program_code] = {
                'loan_amount': row[1],
                'amount_needed_to_purchase': row[2],
                'total_payment': row[3],
                'interest_rate': row[4],
                'apr': row[5],
                'discount_points_percent': row[6]
            }

        # Render the results to the staging_output_file.html template
        return render_template('staging_output_file.html', results=results)

    except Exception as e:
        print(f"Error inserting record or processing scenarios: {e}")
        conn.rollback()
    finally:
        cursor.close()

    return redirect(url_for('form'))


if __name__ == "__main__":
    app.run(debug=True)