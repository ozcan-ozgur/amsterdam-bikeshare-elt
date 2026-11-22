with source as (

    select * from {{ source('donkey_raw', 'system_pricing_plans') }}

),

names as (

    select *
    from {{ source('donkey_raw', 'system_pricing_plans__name') }}
    where language = 'nl'

),

descriptions as (

    select *
    from {{ source('donkey_raw', 'system_pricing_plans__description') }}
    where language = 'nl'

),

renamed as (

    select
        s.plan_id,
        n.text as plan_name,
        d.text as plan_description,
        s.currency,
        s.price,
        s.is_taxable,
        s.url,
        s.fetched_at

    from source as s
    left join names as n
        on s._dlt_id = n._dlt_parent_id
    left join descriptions as d
        on s._dlt_id = d._dlt_parent_id

)

select * from renamed
