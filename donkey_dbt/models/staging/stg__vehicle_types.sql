with source as (

    select * from {{ source('donkey_raw', 'vehicle_types') }}

),


names as (

    select *
    from {{ source('donkey_raw', 'vehicle_types__name') }}
    where language = 'nl'
),


renamed as (

    select
        s.vehicle_type_id,
        s.form_factor,
        s.propulsion_type,
        s.default_pricing_plan_id,
        s.fetched_at,
        n.text as vehicle_type_name

    from source as s
    left join names as n
        on s._dlt_id = n._dlt_parent_id

)

select * from renamed
